from odoo import models, fields


class BKGWarningPREmail(models.TransientModel):
    _name = 'bkg.daily.warning.pr.email'
    
    table_html = fields.Html()