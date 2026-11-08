"""Camera + object detection thread.

Runs a YOLOv8 model exported to ONNX (via onnxruntime + OpenCV only) on
frames pulled from the camera and continuously reports how many objects
are currently visible to the shared Inventory object. Annotated frames
are pushed to a queue for the GUI thread to display.

Deliberately does NOT import `torch` or `ultralytics`: on this Raspberry
Pi, torch's CPU kernels crash with "Instruction non permise" (SIGILL) —
generic PyPI wheels assume CPU instructions this ARM core doesn't have.
onnxruntime's ARM build doesn't have that problem, so all training/export
happens on a dev machine and only the .onnx file + onnxruntime run here.
"""

import queue
import threading
import time

import cv2
import numpy as np
import onnxruntime as ort


class ObjectDetector(threading.Thread):
    def __init__(self, inventory, cfg, frame_queue: "queue.Queue"):
        super().__init__(daemon=True)
        self.inventory = inventory
        self.cfg = cfg
        self.frame_queue = frame_queue
        self._stop_event = threading.Event()
        self._cam = None

    # ------------------------------------------------------------ camera
    def _open_camera(self):
        cfg = self.cfg
        if cfg.CAMERA_SOURCE == "picamera":
            from picamera2 import Picamera2
            picam2 = Picamera2()
            picam2.configure(picam2.create_preview_configuration(
                main={"size": (cfg.FRAME_WIDTH, cfg.FRAME_HEIGHT), "format": "RGB888"},
                # Pin the raw stream to the sensor's native 2x2-binned mode
                # (1640x1232 on the imx219) instead of letting Picamera2
                # default to the larger 1920x1080 raw stream. The bigger
                # default was pushing more data through DMA than needed,
                # which is what the "swiotlb buffer is full" warnings in
                # dmesg were about.
                raw={"size": (1640, 1232)}))
            picam2.start()
            return picam2
        cap = cv2.VideoCapture(cfg.CAMERA_SOURCE)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.FRAME_HEIGHT)
        if not cap.isOpened():
            raise RuntimeError(
                "Could not open camera. Check CAMERA_SOURCE in config.py")
        return cap

    def _read_frame(self, cam):
        if self.cfg.CAMERA_SOURCE == "picamera":
            frame = cam.capture_array()
            return True, frame
        return cam.read()

    def _close_camera(self, cam):
        if hasattr(cam, "release"):
            cam.release()
        elif hasattr(cam, "stop"):
            cam.stop()

    # -------------------------------------------------------- ONNX model
    def _load_model(self):
        session = ort.InferenceSession(
            self.cfg.MODEL_PATH, providers=["CPUExecutionProvider"])
        input_shape = session.get_inputs()[0].shape  # e.g. [1, 3, 640, 640]
        input_size = (int(input_shape[3]), int(input_shape[2]))  # (w, h)
        return session, input_size

    def _preprocess(self, frame, input_size):
        """Letterbox-resize the frame to the model's input size (keeps
        aspect ratio, pads the rest), then convert to the tensor layout
        ONNX expects: 1x3xHxW, RGB, float32 in [0, 1]."""
        in_w, in_h = input_size
        h, w = frame.shape[:2]
        scale = min(in_w / w, in_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(frame, (new_w, new_h))

        canvas = np.full((in_h, in_w, 3), 114, dtype=np.uint8)
        pad_x, pad_y = (in_w - new_w) // 2, (in_h - new_h) // 2
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]  # 1x3xHxW
        return tensor, scale, pad_x, pad_y

    def _postprocess(self, output, scale, pad_x, pad_y, frame_shape):
        """Decode YOLOv8's raw ONNX output (1, 4+num_classes, 8400) into
        boxes in the ORIGINAL frame's coordinates, after NMS."""
        preds = np.squeeze(output).T  # -> (8400, 4+num_classes)
        boxes_xywh = preds[:, :4]
        class_scores = preds[:, 4:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = np.max(class_scores, axis=1)

        keep = confidences >= self.cfg.CONFIDENCE_THRESHOLD
        boxes_xywh, class_ids, confidences = boxes_xywh[keep], class_ids[keep], confidences[keep]
        if len(boxes_xywh) == 0:
            return []

        # cx,cy,w,h (in the padded/resized model input) -> x,y,w,h for NMS
        boxes_xywh_for_nms = boxes_xywh.copy()
        boxes_xywh_for_nms[:, 0] -= boxes_xywh[:, 2] / 2
        boxes_xywh_for_nms[:, 1] -= boxes_xywh[:, 3] / 2

        indices = cv2.dnn.NMSBoxes(
            boxes_xywh_for_nms.tolist(), confidences.tolist(),
            self.cfg.CONFIDENCE_THRESHOLD, self.cfg.NMS_IOU_THRESHOLD)

        h, w = frame_shape[:2]
        detections = []
        for i in np.array(indices).flatten():
            x, y, bw, bh = boxes_xywh_for_nms[i]
            # undo letterbox padding + scaling to map back to the frame
            x1 = (x - pad_x) / scale
            y1 = (y - pad_y) / scale
            x2 = (x + bw - pad_x) / scale
            y2 = (y + bh - pad_y) / scale
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(w, int(x2)), min(h, int(y2))
            detections.append((x1, y1, x2, y2, int(class_ids[i]), float(confidences[i])))
        return detections

    def _draw(self, frame, detections, class_names):
        annotated = frame.copy()
        for x1, y1, x2, y2, cls_id, conf in detections:
            label = f"{class_names.get(cls_id, cls_id)} {conf:.2f}"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 0), 2)
            cv2.putText(annotated, label, (x1, max(0, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1, cv2.LINE_AA)
        return annotated

    # -------------------------------------------------------------- run
    def run(self):
        session, input_size = self._load_model()
        class_names = self.cfg.CLASS_NAMES  # {0: "smd_reel", ...} — see config.py
        cam = self._open_camera()
        self._cam = cam

        frame_idx = 0
        last_annotated = None

        try:
            while not self._stop_event.is_set():
                ok, frame = self._read_frame(cam)
                if not ok or frame is None:
                    time.sleep(0.05)
                    continue

                frame_idx += 1
                if frame_idx % self.cfg.DETECT_EVERY_N_FRAMES == 0:
                    tensor, scale, pad_x, pad_y = self._preprocess(frame, input_size)
                    output = session.run(None, {session.get_inputs()[0].name: tensor})[0]
                    detections = self._postprocess(output, scale, pad_x, pad_y, frame.shape)

                    if self.cfg.CLASSES_OF_INTEREST:
                        detections = [d for d in detections
                                      if class_names.get(d[4]) in self.cfg.CLASSES_OF_INTEREST]

                    self.inventory.set_object_count(len(detections))
                    last_annotated = self._draw(frame, detections, class_names)

                display_frame = last_annotated if last_annotated is not None else frame

                # Keep only the newest frame; the GUI polls faster than it needs.
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
                self.frame_queue.put(display_frame)
        finally:
            # ALWAYS release the camera, even if an exception kills this
            # loop early. Skipping this leaves the Pi's unicam/CSI camera
            # pipeline locked in its last configuration, so the NEXT
            # launch fails with "Failed to start media pipeline: -22"
            # even though nothing is wrong with that later run at all.
            self._close_camera(cam)

    def stop(self):
        self._stop_event.set()
