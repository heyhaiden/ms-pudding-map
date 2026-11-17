import json

from scripts.watch import fresh, issue, listing


def page(products, pages=1):
    data = {"props": {"pageProps": {"viewModel": {"productSearch": {
        "pagination": {"totalPages": pages}, "productLists": {"ranged": products, "unranged": []}}}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


def test_listing_reads_products_and_pages():
    html = page([{"id": "61285843", "seoUrl": "/food/birthday-dot-cake/p/fdp61285843#x", "title": " Birthday Dot Cake ",
                  "imageUrl": "abc.jpg", "weight": "120 g"}], pages=2)
    items, pages = listing(html)
    assert pages == 2
    assert items == [{"id": "61285843", "title": "Birthday Dot Cake", "image": "abc.jpg", "weight": "120 g",
                      "url": "https://www.marksandspencer.com/food/birthday-dot-cake/p/fdp61285843"}]


def test_fresh_skips_seen_and_tracked_and_merges_lists():
    found = [{"id": "1", "lists": ["New In"]}, {"id": "2", "lists": ["New In"]}, {"id": "3", "lists": ["New In"]},
             {"id": "1", "lists": ["As Seen On Social"]}]
    out = fresh(found, seen={"2": {}}, tracked={"3"})
    assert out == [{"id": "1", "lists": ["As Seen On Social", "New In"]}]


def test_issue_is_a_checklist_and_empty_means_none():
    assert issue([], "me") is None
    body = issue([{"id": "9", "title": "Trifle", "url": "u", "image": "", "weight": "1 kg", "lists": ["New In"],
                   "bakery": False}], "me")
    assert body.startswith("@me 1 new dessert ")
    assert "- [ ] [Trifle](u) · 1 kg · New In · id `9`" in body


def test_dessert_keeps_sweet_things_and_drops_savoury_ones():
    from scripts.watch import dessert
    sweet = ["Alcohol Free Christmas Pudding", "Collection Dundee Cake", "Gingerbread Milkshake",
             "Extra Thick Brandy Cream", "Mini Get Your Skis On Colin the Caterpillar",
             "Peppermint Bark Loaded Ice Cream"]
    savoury = ["Pigs In Blankets Yorkshire Pudding Wrap", "Caramelised Onion and Goat's Cheese Tarts",
               "The Merry Pizza Pie", "Non Scratch Sponge Scourers", "Butter Chicken Wings", "Mulling Spices"]
    assert [dessert(t) for t in sweet] == [True] * len(sweet)
    assert [dessert(t) for t in savoury] == [False] * len(savoury)
