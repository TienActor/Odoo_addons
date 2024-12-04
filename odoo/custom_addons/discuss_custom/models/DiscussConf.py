from odoo import models, fields

class DiscussConfigurator(models.TransientModel):
    _inherit = 'res.config.settings'
    
    discuss_setting = fields.Boolean(string='Enable Custom Discuss Sidebar', config_parameter='discuss_custom.discuss_setting')