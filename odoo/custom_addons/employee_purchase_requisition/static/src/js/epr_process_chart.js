//** @odoo-module */
import { registry } from "@web/core/registry";
import { FormRenderer } from "@web/views/form/form_renderer";
import { RelationalModel } from "@web/views/basic_relational_model";
import { FormArchParser } from "@web/views/form/form_arch_parser";
import { FormController } from "@web/views/form/form_controller";
import { FormCompiler } from "@web/views/form/form_compiler";
import { FormControlPanel } from "@web/views/form/control_panel/form_control_panel";
const { Component, onWillStart, onMounted } = owl
import { loadJS, loadCSS } from "@web/core/assets"
import { useService } from "@web/core/utils/hooks";

export class ProcessChartForm extends FormRenderer{
    setup(){
        
        super.setup();
        this.orm = useService("orm");
        this.rpc = useService('rpc');
        this.actionService = useService("action");
        onWillStart(async () =>{
            const arr = []
            const epr_id = this.env.model.root.context.active_id
            var result = await this.rpc(
                '/epr/action_fetch_data',
                {
                    epr_id: epr_id,
                }
            );
            this.data = result
        }) 
        onMounted(async () =>{
            if (this.data.length > 0){
                this.chart = this.createChart(this.data)
            }
            const self = this
            $(document).ready(function(){
                $(".modal-footer").hide();
                $("h2.bkg-h2-process").on( "click", async function() {
                    var type = this.getAttribute("type")
                    var type_id = this.getAttribute("type_id")
                    const action = await self.rpc(
                        '/epr/action_open_window',
                        {
                            type: type,
                            type_id: type_id
                        }
                    );
                    action['res_id'] = parseInt(action['res_id'])
                    self.actionService.doAction(action); 
                });
            });
            // $('ol.breadcrumb li.active').text('Sơ Đồ Tổ Chức');
        })
    }
    createChart(data){
        var org_chart = $('#epr_process_chart').processChart({
            data: data,// your data
            showControls:false,// display add or remove node button.
            allowEdit:false,// click the node's title to edit
            onAddNode:function(node){},
            onDeleteNode:function(node){},
            onClickNode:function(node){},
            newNodeText: ''// text of add button
        });
        return org_chart
    }
    setZoomIn(){
    }
}
export const formView = {
    type: "form",
    display_name:"Form",
    multiRecord: false,
    searchMenuTypes: [],
    ControlPanel: FormControlPanel,
    Controller: FormController,
    Renderer: ProcessChartForm,
    ArchParser: FormArchParser,
    Model: RelationalModel,
    Compiler: FormCompiler,
    buttonTemplate: "web.FormView.Buttons",

    props: (genericProps, view) => {
        const { ArchParser } = view;
        const { arch, relatedModels, resModel } = genericProps;
        const archInfo = new ArchParser().parse(arch, relatedModels, resModel);

        return {
            ...genericProps,
            Model: view.Model,
            Renderer: view.Renderer,
            buttonTemplate: genericProps.buttonTemplate || view.buttonTemplate,
            Compiler: view.Compiler,
            archInfo,
        };
    },
};

registry.category("views").add("epr_process_chart", formView);