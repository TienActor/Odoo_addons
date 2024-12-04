from odoo import models, fields

class DropdownMenu(models.Model):
    _name = 'discuss_custom.dropdown_menu'
    _description = 'Discuss Custom Dropdown Menu'

    name = fields.Char(string='Name', required=True)
    # Add other fields as needed