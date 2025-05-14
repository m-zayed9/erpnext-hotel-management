from frappe.model.document import Document
import frappe


class Booking(Document):
    def before_insert(self):
        self.ensure_customer_exists()

    def ensure_customer_exists(self):
        if not self.customer:
            frappe.throw("Customer name is required to create a new Customer.")

        # Check if a customer exists by customer_name
        customer_name = self.customer  # Temporarily treat it as customer_name
        existing_customer = frappe.get_value("Customer", {"customer_name": customer_name}, "name")

        if not existing_customer:
            new_customer = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": customer_name,
                    "customer_type": "Individual",
                }
            ).insert(ignore_permissions=True)
            self.customer = new_customer.name
        else:
            self.customer = existing_customer  # Link to existing customer.name


    def on_update(self):
        self.create_sales_invoice()

    def create_sales_invoice(self):
        try:
            invoice = frappe.new_doc("Sales Invoice")
            invoice.customer = self.customer
            invoice.due_date = frappe.utils.nowdate()
            invoice.set_posting_time = 1
            invoice.posting_date = frappe.utils.nowdate()

            for room in self.booking_rooms:
                room_doc = frappe.get_doc("Room", room.room_id)
                invoice.append(
                    "items",
                    {
                        "item_code": room_doc.item_id,
                        "qty": room.quantity,
                        "rate": room.price,
                    },
                )

            invoice.insert(ignore_permissions=True)
            invoice.submit()

            self.sales_invoice_id = invoice.name
            self.db_update()

        except Exception as e:
            frappe.throw(f"Failed to create Sales Invoice: {str(e)}")