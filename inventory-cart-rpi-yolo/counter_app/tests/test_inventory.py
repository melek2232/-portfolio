from inventory import Inventory


def test_new_inventory_matches_when_both_counts_are_zero():
    snap = Inventory().snapshot()
    assert snap["object_count"] == 0 and snap["scanned_count"] == 0
    assert snap["match"] is True


def test_add_barcode_counts_it_once():
    inv = Inventory()
    assert inv.add_barcode("A123") is True
    assert inv.add_barcode("A123") is False          # a barcode can never be counted twice
    snap = inv.snapshot()
    assert snap["scanned_count"] == 1
    assert "Duplicate ignored: A123" in snap["log"]


def test_remove_barcode():
    inv = Inventory()
    inv.add_barcode("A123")
    assert inv.remove_barcode("A123") is True
    assert inv.remove_barcode("A123") is False       # already removed
    assert inv.snapshot()["scanned_count"] == 0


def test_match_flag_follows_camera_and_scanner():
    inv = Inventory()
    inv.add_barcode("A")
    inv.add_barcode("B")
    inv.set_object_count(2)
    assert inv.snapshot()["match"] is True
    inv.set_object_count(1)                          # a reel is missing from the cart
    assert inv.snapshot()["match"] is False


def test_reset_clears_scans_but_not_the_camera_count():
    inv = Inventory()
    inv.add_barcode("A")
    inv.set_object_count(3)
    inv.reset()
    snap = inv.snapshot()
    assert snap["scanned_count"] == 0 and snap["object_count"] == 3


def test_log_is_limited_to_the_last_50_events():
    inv = Inventory()
    for i in range(80):
        inv.add_barcode(f"code{i}")
    assert len(inv.snapshot()["log"]) == 50
