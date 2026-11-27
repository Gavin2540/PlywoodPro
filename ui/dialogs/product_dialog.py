"""Add / edit a product. Also opened from the bill editor:

    dlg = ProductDialog(parent)
    if dlg.exec():
        pid = dlg.product_id
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QGridLayout, QWidget

from models import product
from ui import theme
from ui.widgets import Dialog, NumberEdit, button, field, label, restyle, toast
from utils.helpers import format_currency

DEFAULT_TYPES = ["MR", "BWR", "BWP", "Commercial", "Decorative"]
DEFAULT_THICKNESS = ["4mm", "6mm", "8mm", "9mm", "12mm", "16mm", "18mm", "19mm", "25mm"]
DEFAULT_SIZES = ["8x4", "7x4", "6x4", "8x3"]
DEFAULT_UNITS = ["sheets", "sqft", "pieces"]


def _options(column, defaults):
    seen, out = set(), []
    for v in list(defaults) + product.distinct_values(column):
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def _combo(options, placeholder=""):
    cb = QComboBox()
    cb.setEditable(True)
    cb.setInsertPolicy(QComboBox.NoInsert)
    cb.addItems(options)
    cb.setCurrentIndex(-1)
    cb.lineEdit().setPlaceholderText(placeholder)
    return cb


def _set(cb, value):
    cb.setCurrentIndex(-1)
    cb.setEditText("" if value is None else str(value))


class ProductDialog(Dialog):
    def __init__(self, parent, product=None):
        editing = product is not None
        super().__init__(parent, "Edit product" if editing else "Add product",
                         "Prices are per unit. Stock changes through purchases and sales." if not editing else None,
                         ok_text="Save changes" if editing else "Save product", width=660)
        self.product = product
        self.product_id = product["id"] if editing else None

        self.name = _edit_placeholder("e.g. Greenply plywood")
        self.brand = _combo(_options("brand", []), "e.g. Greenply")
        self.type = _combo(_options("type", DEFAULT_TYPES), "e.g. BWP")
        self.thickness = _combo(_options("thickness", DEFAULT_THICKNESS), "e.g. 18mm")
        self.size = _combo(_options("size", DEFAULT_SIZES), "e.g. 8x4")
        self.unit = _combo(_options("unit", DEFAULT_UNITS))
        self.cost = NumberEdit()
        self.price = NumberEdit()
        self.low = NumberEdit(10, placeholder="10")
        self.opening = NumberEdit(0)
        self.margin = label("", "hint", wrap=True)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        for i in range(6):
            grid.setColumnStretch(i, 1)
        top = Qt.AlignTop
        price_field = field("Selling price *", self.price)
        price_field.layout().addWidget(self.margin)
        hint = ("Changing this shifts every stock figure for this product." if editing
                else "Leave 0 if you are starting empty.")
        grid.addWidget(field("Product name *", self.name), 0, 0, 1, 6)
        grid.addWidget(field("Brand", self.brand), 1, 0, 1, 3, top)
        grid.addWidget(field("Type", self.type), 1, 3, 1, 3, top)
        grid.addWidget(field("Thickness", self.thickness), 2, 0, 1, 2, top)
        grid.addWidget(field("Size", self.size), 2, 2, 1, 2, top)
        grid.addWidget(field("Unit", self.unit), 2, 4, 1, 2, top)
        grid.addWidget(field("Cost price *", self.cost, "What you pay per unit"), 3, 0, 1, 3, top)
        grid.addWidget(price_field, 3, 3, 1, 3, top)
        grid.addWidget(field("Opening stock" if editing else "Stock you already have", self.opening, hint),
                       4, 0, 1, 3, top)
        grid.addWidget(field("Low-stock alert at", self.low, "Warn me when stock falls to this level"),
                       4, 3, 1, 3, top)
        holder = QWidget()
        holder.setLayout(grid)
        grid.setContentsMargins(0, 0, 0, 0)
        self.body.addWidget(holder)

        if editing:
            self.name.setText(product.get("name") or "")
            for cb, k in ((self.brand, "brand"), (self.type, "type"), (self.thickness, "thickness"),
                          (self.size, "size"), (self.unit, "unit")):
                _set(cb, product.get(k))
            self.cost.set_value(product.get("purchase_price"))
            self.price.set_value(product.get("selling_price"))
            self.low.set_value(product.get("low_stock_threshold"))
            self.opening.set_value(product.get("opening_stock"))
        else:
            _set(self.unit, "sheets")
            self.add_another = button("Save and add another", None, None, self._save_another)
            self.add_another.setAutoDefault(False)
            self.footer.insertWidget(1, self.add_another)
        self.cost.textChanged.connect(self._update_margin)
        self.price.textChanged.connect(self._update_margin)
        self._update_margin()
        self.on_accept = self.save
        order = [self.name, self.brand, self.type, self.thickness, self.size, self.unit, self.cost, self.price,
                 self.opening, self.low, self.ok_button]
        order += [w for w in (getattr(self, "add_another", None), self.cancel_button) if w]
        for a, b in zip(order, order[1:]):
            QWidget.setTabOrder(a, b)
        self.name.setFocus()

    # ── behaviour ───────────────────────────────────────────────────────
    def _update_margin(self, *_):
        cost, price = self.cost.value(), self.price.value()
        if self.cost.is_blank() and self.price.is_blank():
            self.margin.setText("Margin shows here")
            self.margin.setStyleSheet("")
            return
        diff = price - cost
        pct = f" ({diff / cost * 100:.1f}%)" if cost > 0 else ""
        sign = "-" if diff < 0 else ""
        text = f"Margin {sign}{format_currency(abs(diff))}{pct}"
        if diff < 0:
            text += " · below cost"
        self.margin.setText(text)
        self.margin.setStyleSheet(f"color:{theme.c('bad' if diff < 0 else 'good')};")

    def _values(self):
        return dict(
            name=self.name.text().strip(),
            brand=self.brand.currentText().strip() or None,
            type_=self.type.currentText().strip() or None,
            thickness=self.thickness.currentText().strip() or None,
            size=self.size.currentText().strip() or None,
            purchase_price=self.cost.value(), selling_price=self.price.value(),
            unit=self.unit.currentText().strip() or "sheets",
            low_stock_threshold=self.low.value(), opening_stock=self.opening.value())

    def save(self):
        """Validate and write. Raises ValueError (shown inline) on bad input; returns the product id."""
        if not self.name.text().strip():
            raise ValueError("Product name is required.")
        if self.cost.is_blank():
            raise ValueError("Enter the cost price.")
        if self.price.is_blank():
            raise ValueError("Enter the selling price.")
        v = self._values()
        if self.product_id is None:
            self.product_id = product.add_product(**v)
        else:
            product.update_product(self.product_id, **v)
        app = self.parent()
        if hasattr(app, "data_changed"):
            app.data_changed()
        return self.product_id

    def _save_another(self):
        self.error.hide()
        try:
            self.save()
        except (ValueError, PermissionError) as e:
            self.show_error(e)
            return
        toast(self, "Product saved")
        self.product_id = None
        self.name.clear()
        self.cost.clear()
        self.price.clear()
        self.opening.set_value(0)
        self.name.setFocus()


def _edit_placeholder(text):
    from PySide6.QtWidgets import QLineEdit
    e = QLineEdit()
    e.setPlaceholderText(text)
    return e
