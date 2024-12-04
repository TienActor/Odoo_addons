from odoo import models, fields, api
import openpyxl
from io import BytesIO
import base64
import pandas as pd
import collections

class EPRImportRO(models.TransientModel):
    _name = 'epr.importro'
    
    file_data = fields.Binary(string='File Data', store=False)
    file_name = fields.Char(string='File Name', store=False)
    
    @api.onchange('file_data')
    def onchange_file_data(self):
        if self.file_data and self._context.get('epr_id'):
            try:
                epr = self.env["employee.purchase.requisition"].search([("id","=",self._context.get('epr_id'))])
                        
                ## DOC DU LIEU
                excel_data = base64.b64decode(self.file_data)
                
                # Tạo một đối tượng BytesIO từ dữ liệu bytes
                file_stream = BytesIO(excel_data)
                
                # Sử dụng openpyxl để đọc file Excel
                workbook = openpyxl.load_workbook(file_stream)
                sheet = workbook.active
                
                # Đọc dữ liệu từ sheet
                data = []
                for row in sheet.iter_rows(values_only=True):
                    data.append(row)  
                    
                df = pd.DataFrame(data)
    
                # Đặt tên cột cho DataFrame từ hàng đầu tiên của sheet
                df.columns = df.iloc[0]
                
                # Loại bỏ hàng đầu tiên (tiêu đề cột)
                df = df[1:]
                if 'Product' in df.columns and 'Quantity' in df.columns and 'Description' in df.columns:
                    # Lọc và lấy dữ liệu của hai cột "Product", "Quantity" và "Description"
                    filtered_data = df[["Product", "Quantity", "Description"]]
                else:
                    error_message = 'File Excel Không Đúng Định Dạng'
                    return {
                        'warning': {
                        'title': 'Warning',
                        'message': error_message,
                    }}
                    
                # Tao bien temp de chuyen dataframe sang dict
                temp = filtered_data.T.to_dict('list')
                
                if not temp:
                    error_message = 'Không thể chuyển dữ liệu sang dict.'
                    return {
                        'warning': {
                        'title': 'Warning',
                        'message': error_message,
                    }}
                
                # Tao mang de chua nhung san pham co the tao
                create_product_list = []
                
                # Tao mang de chua nhung san pham co the tao
                create_rorder = []
                
                # Tao mang moi
                my_array = []

                # Thêm danh sách giá trị từ dict vào mảng
                my_array.extend(temp.values())
                
                if not my_array:
                    error_message = 'Dữ Liệu Được Đưa Vào Rỗng.'
                    return {
                        'warning': {
                        'title': 'Warning',
                        'message': error_message,
                    }}
                
                filtered_arr = []
                
                for data in my_array:
                    if data:
                        if data[0]:
                            if data[0].strip():
                                if ')' not in data[0].strip():
                                    error_message = 'Sản Phẩm Sai Định Dạng.'+' Lỗi: '+data[0]
                                    return {
                                        'warning': {
                                        'title': 'Warning',
                                        'message': error_message,
                                    }}
                                    
                                if '(' not in data[0].strip():
                                    error_message = 'Sản Phẩm Sai Định Dạng.'+' Lỗi: '+data[0]
                                    return {
                                        'warning': {
                                        'title': 'Warning',
                                        'message': error_message,
                                    }}
                                
                                if not data[1]:
                                    error_message = 'Số Lượng Không Hợp Lệ.'+' Lỗi: '+data[0]
                                    return {
                                        'warning': {
                                        'title': 'Warning',
                                        'message': error_message,
                                    }}
                                
                                quantity = data[1]
                                    
                                temp = None
                                try:
                                    temp = float(quantity)
                                except:
                                    pass
                                if temp is None or temp <= 0:
                                    error_message = 'Số Lượng Không Hợp Lệ.'+' Lỗi: '+data[0]
                                    return {
                                        'warning': {
                                        'title': 'Warning',
                                        'message': error_message,
                                    }}
                                    
                                product_info = data[0].strip().split("(")
                                product_name = product_info[0].strip()
                                variants = product_info[1].strip().rstrip(")")
                                            
                                if not product_info or not product_name or not variants:
                                    error_message = 'Sản Phẩm Hoặc Biến Thể Bị Rỗng.'+' Lỗi: '+data[0]
                                    return {
                                        'warning': {
                                            'title': 'Warning',
                                            'message': error_message,
                                        }
                                    }
                                    
                                variant = variants.split(',')

                                # Loại bỏ khoảng trắng ở đầu và cuối mỗi phần tử
                                variant = [element.strip() for element in variant]
                                
                                element = {
                                    'name': product_name,
                                    'variant': variant,
                                    'quantity': quantity,
                                }
                                if data[2]:
                                    element['description'] = data[2]
                                
                                filtered_arr.append(element)
                
                # merged_items = []
                # merged_indices = set()

                # for i in range(len(filtered_arr)):
                #     if i in merged_indices:
                #         continue

                #     current_item = filtered_arr[i]
                #     merged_quantity = current_item['quantity']

                #     for j in range(i + 1, len(filtered_arr)):
                #         if j in merged_indices:
                #             continue

                #         if current_item['name'] == filtered_arr[j]['name'] and current_item['variant'] == filtered_arr[j]['variant']:
                #             merged_quantity += filtered_arr[j]['quantity']
                #             merged_indices.add(j)

                #     current_item['quantity'] = merged_quantity
                #     merged_items.append(current_item)
                
                for data in filtered_arr:
                    
                    products = self.env["product.template"].search([('name', '=', data['name'])])
                            
                    if not products:
                        error_message = 'Sản Phẩm Không Tồn Tại.'+' Lỗi: '+data['name']+'('+', '.join(str(i) for i in data['variant'])+')'
                        return {
                            'warning': {
                                'title': 'Warning',
                                'message': error_message,
                            }
                        }
                            
                    attrs_arr = []
                    
                    product = None
                    
                    attr = None
                    
                    for p in products:
                        attrs = self.env["product.template.attribute.line"].search([('product_tmpl_id','=',p.id)])
                        if len(data['variant']) == len(attrs):
                            product = p
                            attr = attrs
                        attrs_arr.append(len(attrs))
                    check_attrs_duplicate = [item for item, count in collections.Counter(attrs_arr).items() if count > 1]
                    
                    if check_attrs_duplicate:
                        error_message = 'Trong Cơ Sở Dữ Lệu Có 2 Sản Phẩm Trở Lên Có Cùng Tên Và Cùng Số Lượng Biến Thể.'+' Lỗi: '+data['name']+'('+', '.join(str(i) for i in data['variant'])+')'
                        return {
                            'warning': {
                                'title': 'Warning',
                                'message': error_message,
                            }
                        }
                            
                    ## Kiem tra du thuoc tinh bien the cua san pham hay chua
                    if not product or not attr:
                        error_message = 'Sản Phẩm '+data['name']+' Không Có Biến Thể Nào '+str(len(data['variant']))+' Thuộc Tính. Lỗi: '+data['name']+'('+', '.join(str(i) for i in data['variant'])+')'
                        return {
                            'warning': {
                                'title': 'Warning',
                                'message': error_message,
                            }
                        }
                        
                    values = []  
                       
                    ## Kiem tra gia tri bien the theo thu tu
                    for v,a in zip(data['variant'],attr):
                                    
                        variant_value = self.env["product.attribute.value"].search([("attribute_id", "=", a.attribute_id.id),('name', '=', v)])
                                    
                        # Kiem tra neu gia tri bien the khong co trong co
                        if not variant_value: 
                            error_message = 'Không Có Giá Trị ('+ str(v)+') Trong Biến Thể ('+str(a.attribute_id.name)+').'+ ' Lỗi: '+data['name']+'('+', '.join(str(i) for i in data['variant'])+')'
                            return {
                                'warning': {
                                'title': 'Warning',
                                'message': error_message,
                            }}
                        else: values.append(variant_value)
                                    
                    # Kiem tra values va product template attribute value
                    if values:
                        ptavs = []  
                        for value in values:
                            temp = self.env["product.template.attribute.value"].search(
                                [
                                    (
                                        "product_tmpl_id",
                                        "in",
                                        [
                                            product.id
                                        ],
                                    ),
                                    (
                                        "product_attribute_value_id",
                                        "in",
                                        [
                                            value.id
                                        ],
                                    ),
                                ]
                            )
                            if temp:
                                ptavs.append(temp.id)
                            else:
                                error_message = 'Biến Thể ('+value.name+') Chưa Được Settings.'+' Lỗi: '+data['name']+'('+', '.join(str(i) for i in data['variant'])+')'
                                return {
                                    'warning': {
                                        'title': 'Warning',
                                        'message': error_message,
                                    }
                                }
                                
                        # Dinh dang lai combination_indices de kiem tra
                        result = ptavs
                                
                        result.sort()
                                
                        if len(ptavs) > 1:
                            string_list = [str(num) for num in result]
                            result = ','.join(string_list)
                                
                        product_variant = self.env["product.product"].search([("combination_indices", "=", result)])
                        
                        description = None
                        if 'description' in data: description = data['description']
                        
                        ## Neu da co bien the, tao stock move, neu chua co thi tao bien the va stock move
                        if not epr:
                            error_message = 'Lỗi Không Tìm Được Employee Purchase Requisition.'
                            return {
                                'warning': {
                                'title': 'Warning',
                                'message': error_message,
                            }} 
                            
                        if product_variant:
                            ROrder_new = {
                                'product_id': product_variant.id,
                                'quantity': data['quantity'],
                                'create_uid': self.env.user.id,
                                'write_uid': self.env.user.id,
                                'requisition_product_id': epr.id,
                            }
                            if description:
                                ROrder_new['description'] = description
                            create_rorder.append(ROrder_new)
                            
                        elif not product_variant:
                            new_product_create = {
                                'attribute_line_ids': [(4, x.id, False) for x in attr],
                                'product_tmpl_id': product.id,
                                'sale_ok': True,
                                'purchase_ok': True,
                                'active': True,
                                'default_code': False,
                                'barcode': False,
                                'weight': 0,
                                'volume': 0,
                                'product_template_attribute_value_ids': [(4, x) for x in ptavs]}
                            
                            ROrder_new_create = {
                                'quantity': data['quantity'],
                                'create_uid': self.env.user.id,
                                'write_uid': self.env.user.id,
                                'requisition_product_id': epr.id,
                            }
                            if description: ROrder_new_create['description'] = description
                            
                            new_attrs = {
                                'product_create': new_product_create,
                                'rorder_create': ROrder_new_create,
                                'combination_indices': result
                            }
                                
                            create_product_list.append(new_attrs)
                            
                # Tao Product
                for product in create_product_list:
                    rorder_create = product['rorder_create']
                    product_create = self.env["product.product"].search([("combination_indices", "=", product.get('combination_indices'))])
                    if len(product_create) == 1:
                        rorder_create['product_id'] = product_create.id
                    elif len(product_create) == 0:
                        product_create = self.env['product.product'].create(product['product_create'])
                        rorder_create['product_id'] = product_create.id
                    if rorder_create['product_id']:
                        self.env['requisition.order'].create(rorder_create)
                        
                # Tao StockMove                
                for rorder in create_rorder:
                    self.env["requisition.order"].create(rorder)
                    
            except FileNotFoundError:
                print("Không tìm thấy tệp Excel.")
            except pd.errors.ParserError:
                print("Tệp không phải là tệp Excel.")
            except ValueError as e:
                print(str(e))
            
            error_message = 'Đọc Và Tạo Dữ Liệu Thành Công'
            return {
                'warning': {
                'title': 'Thông Báo',
                'message': error_message,
            }} 
            
    def close_modal(self):
        return {
            'type': 'ir.actions.act_window_close'
        } 
    
    def download_example_file(self):
        url = 'https://drive.google.com/uc?id=1nCf5wZ4rJEvVnLpPALdQbKPotkPKn88K&export=download'
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': url
        }           
        