"""Fill a database with realistic demo data for trying the app.

    python tools/seed_demo.py [path-to-db]      (default: data/demo.db)
"""
import datetime, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import DatabaseManager
from models import bills, expense, product, settings, stock


def seed(path):
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    DatabaseManager.initialize(path)
    rnd = random.Random(7)
    today = datetime.date.today()
    settings.set_many({"shop_name": "Sri Lakshmi Plywoods", "shop_address": "14 Timber Yard Road, Hyderabad 500012",
                       "shop_phone": "98480 12345", "shop_gstin": "36ABCDE1234F1Z5"})
    catalog = [
        ("Marine Ply", "Greenply", "BWP", "18mm", "8x4", 2350, 2890), ("Marine Ply", "Greenply", "BWP", "12mm", "8x4", 1680, 2050),
        ("Club Prime", "Century", "BWR", "18mm", "8x4", 2100, 2540), ("Club Prime", "Century", "BWR", "9mm", "8x4", 1190, 1450),
        ("Sainik MR", "Century", "MR", "18mm", "8x4", 1520, 1860), ("Sainik MR", "Century", "MR", "6mm", "8x4", 640, 790),
        ("Block Board", "Kitply", "Commercial", "19mm", "8x4", 1750, 2120), ("Flexi Ply", "Archidply", "MR", "8mm", "8x4", 980, 1240),
        ("Laminate Sheet", "Merino", "Decorative", "1mm", "8x4", 890, 1150), ("MDF Board", "Action Tesa", "Interior", "17mm", "8x4", 1320, 1590),
        ("Teak Veneer", "Greenlam", "Decorative", "4mm", "8x4", 1850, 2400), ("Shuttering Ply", "Kitply", "Commercial", "12mm", "8x4", 1100, 1330),
    ]
    start = today - datetime.timedelta(days=75)
    ids = [product.add_product(*c, "sheets", rnd.choice([8, 10, 12, 15]), rnd.choice([0, 0, 20, 35])) for c in catalog]
    suppliers = ["Century Plyboards Depot", "Greenply Distributors", "Balaji Timber Traders", "Kitply Agencies"]
    customers = ["Ravi Interiors", "Sai Constructions", "Lakshmi Furniture Works", "Anand Carpentry", "Venkat & Sons", "Modern Kitchens"]
    day = start
    while day <= today:
        if day.weekday() != 6:
            if rnd.random() < 0.3 or day == start:
                picks = rnd.sample(range(len(ids)), rnd.randint(2, 5))
                items = [{"product_id": ids[i], "qty": rnd.choice([20, 30, 40, 50, 60]), "unit_price": catalog[i][5] * rnd.uniform(0.97, 1.03) // 1} for i in picks]
                total = sum(i["qty"] * i["unit_price"] for i in items)
                bills.save_bill("purchase", day, items, party_name=rnd.choice(suppliers),
                                paid=total if rnd.random() < 0.6 else round(total * rnd.choice([0, 0.5]), 0))
            for _ in range(rnd.randint(1, 5)):
                levels = stock.stock_map(day)
                picks = [i for i in rnd.sample(range(len(ids)), rnd.randint(1, 3)) if levels[ids[i]] >= 3]
                items = [{"product_id": ids[i], "qty": min(rnd.choice([1, 2, 3, 4, 6, 8, 10]), int(levels[ids[i]])),
                          "unit_price": catalog[i][6] * rnd.uniform(0.96, 1.04) // 1} for i in picks]
                if not items:
                    continue
                total = sum(i["qty"] * i["unit_price"] for i in items)
                walk_in = rnd.random() < 0.35
                try:
                    bills.save_bill("sale", day, items, party_name=None if walk_in else rnd.choice(customers),
                                    discount=rnd.choice([0, 0, 0, 100, 250]) if total > 5000 else 0,
                                    paid=None if walk_in or rnd.random() < 0.6 else round(total * rnd.choice([0, 0.4, 0.5]), 0))
                except stock.StockError:
                    pass
            for cat, lo, hi, chance in (("Transport", 300, 1800, .5), ("Labour", 400, 1200, .6), ("Loading", 150, 600, .35), ("Miscellaneous", 80, 500, .15)):
                if rnd.random() < chance:
                    expense.insert_expense(day, cat, rnd.randint(lo, hi) // 10 * 10, "")
            if day.day == 1:
                expense.insert_expense(day, "Rent", 25000, "Shop rent")
                expense.insert_expense(day, "Salary", 32000, "Staff salaries")
        day += datetime.timedelta(days=1)
    stock.set_count(ids[5], today - datetime.timedelta(days=9), max(0, stock.stock_on(ids[5], today - datetime.timedelta(days=9)) - 2), "2 sheets water damaged")
    for n in range(20, 30):
        stock.lock_day(today - datetime.timedelta(days=n))
    DatabaseManager.close()
    return path


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("Seeded", seed(sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "data", "demo.db")))
