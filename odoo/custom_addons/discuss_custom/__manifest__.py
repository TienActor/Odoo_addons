# -*- coding: utf-8 -*-
{
    'name': 'Discuss Custom',
    'version': '1.0',
    'category': 'Discuss',
    'summary': 'Customizations for Discuss module',
    'description': """
        This module adds custom features to the Discuss module.
    """,
    'depends': [ 'base','mail'],
    'data': [
        'security/my_module_security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml', 
        'security/view_setting.xml',
    ],
    'assets': {
        'web.assets_backend': [ 
            'discuss_custom/static/src/js/discuss_custom.js',
            'discuss_custom/static/src/css/discuss_custom.css',
            'discuss_custom/static/src/xml/discuss_custom_sidebar.xml',

        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}