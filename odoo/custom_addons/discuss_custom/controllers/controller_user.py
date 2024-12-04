# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request, route
from odoo import SUPERUSER_ID

class UserDropdownController(http.Controller):

  
  
    @http.route('/search_users', type='json', auth="user")
    def search_users(self, search_term):
        try:
            users = request.env['res.partner'].sudo().search_read(
            [('is_company', '=', False), ('active', '=', True), ('type', '=', 'contact'), ('name', 'ilike', search_term)],
            ['id', 'name'],
            limit=10
        )
            return {
                'users': [{'id': user['id'], 'name': user['name']} for user in users]
            }
        except Exception as e:
            return {'error': str(e)}


    @http.route('/get_mail_channels_tien/<int:user_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def get_channels(self, user_id):
        if not user_id:
            return {'error': 'Partner ID is required'}
        
        # Thực hiện truy vấn an toàn hơn với các placeholder
        query = """
            SELECT mc.id, mc.name, mc.channel_type ,mc.description
            FROM mail_channel mc
            JOIN mail_channel_member mcm ON mc.id = mcm.channel_id
            JOIN res_partner rp ON mcm.partner_id = rp.id
            WHERE rp.id = %s;
        """
        request.env.cr.execute(query, (user_id,))
        channels = request.env.cr.dictfetchall()

        # Trả về kết quả hoặc một mảng rỗng nếu không có kết quả
        return {'channels': channels}


    @http.route('/get_mail_channel_info', type='json', auth='user', methods=['POST'], csrf=False)
    def get_mail_channel_info(self, channel_id):
       
        channel = request.env['mail.channel'].sudo().search([('id', '=', channel_id)], limit=1)
        if not channel:
            print("Channel not found")
            return {'error': 'Channel not found'}
        
        result = {
            'id': channel.id,
            'name': channel.name,
            'type': channel.channel_type,
            'description': channel.description or 'No description provided.'
        }
       
        return result


    @http.route(['/tien/chat_full_history'], type="json", auth="user", cors="*")
    def mail_chat_full_history(self, channel_id, limit=100):
        try:
            channel = request.env["mail.channel"].sudo().search([('id', '=', channel_id)])
            if not channel:
                return {"error": "Channel not found"}

            # Truy vấn tin nhắn
            messages = request.env['mail.message'].sudo().search_read(
                [('model', '=', 'mail.channel'), ('res_id', '=', channel.id)],
                ['id', 'body', 'date', 'author_id', 'create_uid', 'write_date','parent_id'],
                limit=limit,
                order='date asc'
            )

            # Truy vấn attachments
            query = """
                SELECT ir.id, ir.create_uid, ir.name, ir.res_model, ir.mimetype, mm.id as message_id
                FROM ir_attachment ir
                JOIN mail_message mm ON ir.write_date = mm.write_date
                WHERE mm.model = 'mail.channel' AND mm.res_id = %s AND ir.res_model = 'mail.channel'
            """
            request.env.cr.execute(query, (channel_id,))
            attachments = request.env.cr.dictfetchall()

            # Gán attachments vào tin nhắn tương ứng
            attachment_dict = {}
            for attachment in attachments:
                if attachment['message_id'] not in attachment_dict:
                    attachment_dict[attachment['message_id']] = []
                attachment_dict[attachment['message_id']].append({
                    'id': attachment['id'],
                    'name': attachment['name'],
                    'mimetype': attachment['mimetype']
                })

            for message in messages:
                message['attachments'] = attachment_dict.get(message['id'], [])

                # Xử lý thông tin reply
                if message['parent_id']:
                    parent_message = request.env['mail.message'].sudo().browse(message['parent_id'][0])
                    message['reply_to'] = {
                        'id': parent_message.id,
                        'body': parent_message.body,
                        'author_name': parent_message.author_id.name,
                        'author_id': parent_message.author_id.id,
                    }

            return {"messages": messages}
        except Exception as e:
            return {"error": str(e)}

    # Lấy member channel
    @http.route('/get_chat_group_members', type='json', auth='user')
    def get_chat_group_members(self, channel_id):
        channel = request.env['mail.channel'].browse(channel_id)
        if not channel:
            return {'error': 'Channel not found'}
    
        members = channel.channel_partner_ids.read(['id', 'name', 'image_128'])
        return {'members': members}

    # kiểm tra quyền discuss manager
    @http.route('/check_discuss_custom_permissions', type='json', auth="user")
    def check_discuss_custom_permissions(self):
        user = request.env.user
        return {
        'permissions': {
            'isAdmin': user.has_group('discuss_custom.group_discuss_custom_admin'),
            # 'isUser': user.has_group('discuss_custom.group_discuss_custom_user')
        }
    }

    
 

    



            