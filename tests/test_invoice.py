import datetime
import os

from models import bills, product, settings
from utils.invoice import invoice_pdf

TODAY = datetime.date.today().isoformat()


def _product(name="Ply <18> & Sons"):
    return product.add_product(name, "A&B", "BWP", "18mm", "8x4", 1000, 1300, "sheets", 5, 50)


def _check(path):
    data = open(path, "rb").read()
    assert data.startswith(b"%PDF") and len(data) > 1500
    return data


def test_sale_invoice_with_discount_and_part_payment(db, tmp_path):
    settings.set_many({"shop_name": "Sri & Co <Plywoods>", "shop_gstin": "36ABCDE1234F1Z5", "invoice_footer": "Thanks & visit again"})
    p = _product()
    b = bills.save_bill("sale", TODAY, [{"product_id": p, "qty": 4, "unit_price": 1300}], party_name="Ravi & <Sons>",
                        party_phone="98765", discount=200, paid=2000, notes="Deliver <soon>")
    bills.add_payment(b, 500, method="UPI")
    out = str(tmp_path / "s.pdf")
    assert invoice_pdf(b, out) == out
    _check(out)


def test_purchase_record_without_shop_details(db, tmp_path):
    p = _product()
    b = bills.save_bill("purchase", TODAY, [{"product_id": p, "qty": 10, "unit_price": 1000}], party_name="Century & Co")
    out = str(tmp_path / "p.pdf")
    invoice_pdf(b, out)
    assert os.path.getsize(out) > 1500
    _check(out)
