//오류 메세지 override
Ext.define('Site.override.ServerExceptionHandler', {
	override : 'Cmmn.ServerExceptionHandler',
	defaultExceptionsHandler : function(exceptions) {
		Ext.create('Ext.window.Window', {
			title : '#{Error}',
			height : 400,
			width : 600,
			minHeight : 200,
			minWidth : 300,
			autoShow : true,
			layout : 'fit',
			modal : true,
			items : [ {
				xtype : 'gridpanel',
				hideHeaders : true,
				scroll : 'vertical',
				columns : [ {
					dataIndex : 'message',
					flex : 1,
					renderer: function(value, metaData, record, rowIndex, colIndex, store, view) {
						if(!value){
							return '네트워크 상태가 불안정 합니다. <br/> 다시 시도해 주시길 바랍니다.';
						}
						return value;
					}
				} ],
				store : Ext.create('Ext.data.Store', {
					fields : [ 'message' ],
					data : exceptions
				}),
				plugins : [ {
					ptype : 'rowexpander',
					rowBodyTpl : '<pre style="overflow-x:auto;">{where}</pre>'
				} ]
			} ],
			dockedItems : [ {
				xtype : 'toolbar',
				dock : 'bottom',
				items : [ {
					xtype : 'tbspacer',
					flex : 1
				}, {
					xtype : 'button',
					text : Ext.Msg.buttonText.ok,
					handler : function(btn) {
						btn.up('window').close();
					}
				}, {
					xtype : 'tbspacer',
					flex : 1
				} ]
			} ]
		});
	}
});