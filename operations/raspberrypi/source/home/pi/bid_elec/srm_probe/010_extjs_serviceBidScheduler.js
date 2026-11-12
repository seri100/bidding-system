/**
 *  [호출 예제]
 * 
{
	xtype: 'button',
	iconCls: 'btn-search',
	text: '#{일괄적용}',
	listeners:{
		click: function(){
			var me = this.up('REDACTED_LONG_LITERAL');
			
			me.setLoading(true); // 로딩바 생성
			Ext.defer(function(){
				var popup = Ext.create('Kepco.panel.Date'),
    				vm = me.getViewModel(),
    				alwaysAttendYn = me.down('etnatogglefield[itemId=alwaysAttendYn]'), // itemId:alwaysAttendYn 적용
    				form = me.lookupReference('bidProgress'), // datefield, numberfield의 Container
    				datefields = form.query('datefield'), // datefield 검색
    				numberfields = form.query('numberfield'), // numberfield 검색(시,분)
    				bidData = vm.get('bidData');
    			
    			var dateFieldGroups={}, numberFieldsGroups={}, toggleField={};
    			
    			Ext.each(datefields, function(field){
    				var fieldContainer = field.up('fieldcontainer');
    				dateFieldGroups[field.itemId] = {
    						'label': fieldContainer.fieldLabel, // datefield의 라벨
    						'visible': !(fieldContainer.hidden), // datefield의 visible 여부
    						'minValue': field.minValue, // datefield의 minValue
    						'maxValue': field.maxValue // datefield의 maxValue
    				};
    			});
    			
    			Ext.each(numberfields, function(field){
    				numberFieldsGroups[field.itemId] = {
    						'readOnly': field.readOnly
    				};
    			});
    			
    			//토글버튼 속성
    			toggleField.readOnly = alwaysAttendYn.readOnly;
    			
    			popup.setComponentState(dateFieldGroups, numberFieldsGroups, toggleField); // 컴포넌트 상태 변경
    			popup.setParameter(bidData); // 파라미터 전달
    			popup.show();
    			
    			// 1. Validation 펑션 호출(with returnValue)
    			popup.on('applydates', function(returnValue){
					// 2. afterapplydates를 무조건 호출
					popup.fireEvent('afterapplydates', {result:true, message:'성공적으로 적용하였습니다.'});
    			});
    			
    			popup.on('afterpickerchange', function(param){
    				var dateDate = param.dateDate,
    					changedFieldId = param.changedFieldId;
    				
    				// popup.setParameter();
    			}, me);
    			
    			me.setLoading(false);
			}, 10);
		}
	}
}
*/

Ext.define('Kepco.panel.Date', {
	extend: 'Ext.panel.Panel',
	requires: [
		'Ext.form.RadioGroup',
		'Ext.view.BoundList',
		'Ext.form.field.Display',
        'Ext.form.field.Number',
	],
	alias : 'widget.kepcopaneldate',
	
	viewModel: {
		data: {
	    	dateData: null
	    }
	},
	style:{
		background: 'white'
	},
	closeAction: 'hide',
	referenceHolder: true,
	modal: true,
	floating: true,
	draggable: true,
	width: 900,
	
	enableBubble: true,
	moveScrollYSize: 21,
	padding: 5,
    title: '#{시작일/종료일}',
    layout: {
        type: 'vbox',
        align: 'stretch'
    },
    bodyStyle:{ 
    	/** Panel의 body style 속성 적용 */
    	border: '1px solid #c3cbd1'
    },
    
    /** Value Change Event를 발생할 특정 필드의 itemId_t */
    fireChangeEventFields: [
    	'bidAttendRequestCloseDateTime',
    	'beginDateTime',
    	'specProposalBeginDateTime'
    ],
    
    /** RadioField 선택 시, CSS */
    selectBorderWidth: '2px',
    selectBorderColor: '#3892d3',
    deselectBorderColor: '#FFFFFF',
    
    /** Text */
    startDatePickerTitle: '#{시작일시}',
	endDatePickerTitle: '#{마감일시}',
	hourText: Ext.String.format('#{시}'),
	minuteText: Ext.String.format('#{분}'),
    

	/** Title CSS */
	headerCSS : {
		'fontWeight': 'bold'
	},
	
    initComponent: function(){
    	var me = this;
    	
    	me.items = [
			{
				xtype: 'form',
			    reference: 'kepcoDateForm',
			    itemId: 'kepcoDateForm',
			    bodyPadding: 10,
			    margin: '5',
			    layout: {
			        type: 'vbox',
			        align: 'stretch'
			    },
			    dockedItems: [
			                  {
			                      xtype: 'toolbar',
			                      colspan: 2,
			                      dock: 'top',
			                      ui: 'search',
			                      items: [
			                          {
			                              xtype: 'tbspacer',
			                              flex: 1
			                          },
			                          {
			                              xtype: 'button',
			                              iconCls: 'btn-search',
			                              text: '#{적용}',
			                              listeners:{
			                            	  click: {
			                            		  scope: me,
			                            		  fn: function(){
			                            			  var me = this;
			                            			  me.applyDates();
				                            	  }
				                              }
			                              }
			                          },
			                          {
			                              xtype: 'button',
			                              iconCls: 'btn-close',
			                              text: '#{닫기}',
			                              listeners:{
			                            	  click: {
			                            		  scope: me,
			                            		  fn: function(){
			                            			  var me = this;
			                            			  me.close();
			                            		  }
			                            	  }
			                              }
			                          }
			                      ]
			                  }
			              ],
			    items: [
	            	{
	            		xtype: 'container',
	            		layout: {
					        type: 'hbox',
					        align: 'stretch'
					    },
					    style: {
					    	padding:'5 5 5 5px'
			    		},
					    hasRadio: true,
	            		items:[
	            			{
	            				xtype: 'radiofield',
	            				margin: '4 0 0 0',
	            				width: 25,
	            				checked: true,
	            				labelAlign: 'top',
            					style: {
            						padding:'3px'
            					}
	            			
	            			},
	            			{
							    xtype: 'fieldcontainer',
							    layout: {
							        type: 'table',
							        columns: 7
							    },
							    style: {
							    	'border-width': me.selectBorderWidth,
							    	'border-color': me.deselectBorderColor,
							    	'border-style': 'solid'
							    },
							    defaults: {
							    	padding:'3px',
							    	margin: '5'
					    		},
							    items: [
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{입찰공고 시작일시}',
							            readOnly: true,
							            itemId_t: 'noticeDate',
							            bind: {
							            	value: '{dateData.noticeDate}'
							            },
//									            format: 'Y/m/d H:i',
							            format: 'Y/m/d',
							            labelWidth: 170,
							            width: 270,
							            labelAlign: 'left',
							            name: 'startDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateHour',
                                        itemId_t: 'noticeDateHour',
                                        bind: {
                                            value: '{dateData.noticeDateHour}'
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateMinute',
                                        itemId_t: 'noticeDateMinute',
                                        bind: {
                                            value: '{dateData.noticeDateMinute}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: 0,
                                        text: me.minuteText
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '5',
                                        style:{
							            	'color': 'white'
							            },
                                        text: '~'
                                    }
							    ]
							},
							{
                                xtype: 'etnatogglefield',
                                fieldLabel: '#{상시투찰적용여부}',
                                itemId_t: 'alwaysAttendYn',
                                labelWidth: 170,
                                onText: '#{적용}',
                                offText: '#{미적용}',
                                onValue: true,
                                offValue: false,
                                width: 290,
                                padding:'3px',
						    	margin: '5',
					            labelAlign: 'left',
                                scale: 'small',
                                bind: {
                                    value: '{dateData.alwaysAttendYn}'
                                },
                                listeners: {
                                    change: 'onEtnatogglefieldChange',
                                    scope: me
                                }
                            }
	            		]
	            	},
	            	{
	            		xtype: 'container',
	            		layout: {
					        type: 'hbox',
					        align: 'stretch'
					    },
					    style: {
					    	padding:'5 5 5 5px'
			    		},
					    hasRadio: true,
	            		items:[
							{
								xtype: 'radiofield',
								margin: '4 0 0 0',
								width: 25,
								labelAlign: 'top',
								style: {
							    	padding:'3px'
					    		},
							},
							{
							    xtype: 'fieldcontainer',
							    layout: {
							        type: 'table',
							        columns: 11
							    },
							    defaults: {
							    	padding:'3px',
							    	margin: '5'
					    		},
					    		style: {
							    	'border-width': me.selectBorderWidth,
							    	'border-color': me.deselectBorderColor,
							    	'border-style': 'solid'
							    },
							    items: [
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{PQ심사접수 시작일시}',
							            itemId_t: 'pqEvalStartDateTime',
							            readOnly: true,
							            bind: {
							            	value: '{dateData.pqEvalStartDateTime}'
							            },
							            format: 'Y/m/d',
							            labelWidth: 170,
							            width: 270,
							            labelAlign: 'left',
							            name: 'startDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateHour',
                                        itemId_t: 'pqEvalStartDateHour',
                                        bind: {
                                            value: '{dateData.pqEvalStartDateHour}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateMinute',
                                        itemId_t: 'pqEvalStartDateMinute',
                                        bind: {
                                            value: '{dateData.pqEvalStartDateMinute}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: 0,
                                        text: me.minuteText
                                    },
							        {
                                        xtype: 'label',
                                        margin: '5',
                                        text: '~'
                                    },
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{PQ심사접수 마감일시}',
							            readOnly: true,
							            itemId_t: 'pqEvalCloseDateTime',
							            bind: {
							            	value: '{dateData.pqEvalCloseDateTime}'
							            },
							            format: 'Y/m/d',
							            labelWidth: 170,
							            width: 270,
							            labelAlign: 'left',
							            name: 'endDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'endDateHour',
                                        itemId_t: 'pqEvalCloseDateHour',
                                        bind: {
                                            value: '{dateData.pqEvalCloseDateHour}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'endDateMinute',
                                        itemId_t: 'pqEvalCloseDateMinute',
                                        bind: {
                                            value: '{dateData.pqEvalCloseDateMinute}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: 0,
                                        text: me.minuteText
                                    }
							    ]
							}
	        			],
	        		},
	            	{
	            		xtype: 'container',
	            		layout: {
					        type: 'hbox',
					        align: 'stretch'
					    },
					    style: {
					    	padding:'5 5 5 5px'
			    		},
					    hasRadio: true,
	            		items:[
							{
								xtype: 'radiofield',
								margin: '4 0 0 0',
								width: 25,
								labelAlign: 'top',
								style: {
							    	padding:'3px'
					    		},
							},
							{
							    xtype: 'fieldcontainer',
							    layout: {
							        type: 'table',
							        columns: 11
							    },
							    style: {
							    	'border-width': me.selectBorderWidth,
							    	'border-color': me.deselectBorderColor,
							    	'border-style': 'solid'
							    },
							    defaults: {
							    	padding:'3px',
							    	margin: '5'
					    		},
							    items: [
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{입찰참가신청 시작일시}',
							            labelWidth: 170,
							            width: 270,
							            readOnly: true,
							            itemId_t: 'bidAttendRequestBeginDateTime',
							            bind: {
							            	value: '{dateData.bidAttendRequestBeginDateTime}'
							            },
							            format: 'Y/m/d',
							            labelAlign: 'left',
							            name: 'startDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateHour',
                                        itemId_t: 'bidAttendRequestBeginDateHour',
                                        bind: {
                                            value: '{dateData.bidAttendRequestBeginDateHour}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateMinute',
                                        itemId_t: 'bidAttendRequestBeginDateMinute',
                                        bind: {
                                            value: '{dateData.bidAttendRequestBeginDateMinute}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: 0,
                                        text: me.minuteText
                                    },
							        {
                                        xtype: 'label',
                                        margin: '5',
                                        text: '~'
                                    },
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{입찰참가신청 마감일시}',
							            labelWidth: 170,
							            width: 270,
							            readOnly: true,
							            itemId_t: 'bidAttendRequestCloseDateTime',
							            bind: {
							            	value: '{dateData.bidAttendRequestCloseDateTime}'
							            },
							            format: 'Y/m/d',
							            labelAlign: 'left',
							            name: 'endDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        reference: 'bidAttendRequestCloseDateHour',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'endDateHour',
                                        itemId_t: 'bidAttendRequestCloseDateHour',
                                        bind: {
                                            value: '{dateData.bidAttendRequestCloseDateHour}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        reference: 'bidAttendRequestCloseDateMinute',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'endDateMinute',
                                        itemId_t: 'bidAttendRequestCloseDateMinute',
                                        bind: {
                                            value: '{dateData.bidAttendRequestCloseDateMinute}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.minuteText
                                    }
							    ]
							}
	        			],
	        		},
	        		{
	            		xtype: 'container',
	            		layout: {
					        type: 'hbox',
					        align: 'stretch'
					    },
					    style: {
					    	padding:'5 5 5 5px'
			    		},
					    hasRadio: true,
	            		items:[
							{
								xtype: 'radiofield',
								margin: '4 0 0 0',
								width: 25,
								labelAlign: 'top',
								style: {
							    	padding:'3px'
					    		},
							},
							{
							    xtype: 'fieldcontainer',
							    layout: {
							        type: 'table',
							        columns: 11
							    },
							    defaults: {
							    	padding:'3px',
							    	margin: '5'
					    		},
					    		style: {
							    	'border-width': me.selectBorderWidth,
							    	'border-color': me.deselectBorderColor,
							    	'border-style': 'solid'
							    },
							    items: [
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{입찰서제출 시작일시}',
							            readOnly: true,
							            itemId_t: 'beginDateTime',
							            bind: {
							            	value : '{dateData.beginDateTime}'
							            },
							            format: 'Y/m/d',
							            labelWidth: 170,
							            width: 270,
							            labelAlign: 'left',
							            name: 'startDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateHour',
                                        itemId_t: 'beginDateHour',
                                        bind: {
                                            value: '{dateData.beginDateHour}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateMinute',
                                        itemId_t: 'beginDateMinute',
                                        bind: {
                                            value: '{dateData.beginDateMinute}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: 0,
                                        text: me.minuteText
                                    },
							        {
                                        xtype: 'label',
                                        margin: '5',
                                        text: '~'
                                    },
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{입찰서제출 마감일시}',
							            readOnly: true,
							            itemId_t: 'endDateTime',
							            bind: {
							            	value : '{dateData.endDateTime}'
							            },
							            format: 'Y/m/d',
							            labelWidth: 170,
							            width: 270,
							            labelAlign: 'left',
							            name: 'endDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'endDateHour',
                                        itemId_t: 'endDateHour',
                                        bind: {
                                            value: '{dateData.endDateHour}'
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'endDateMinute',
                                        itemId_t: 'endDateMinute',
                                        bind: {
                                            value: '{dateData.endDateMinute}'
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.minuteText
                                    }
							    ]
							}
	        			],
	        		},
	        		{
	            		xtype: 'container',
	            		layout: {
					        type: 'hbox',
					        align: 'stretch'
					    },
					    style: {
					    	padding:'5 5 5 5px'
			    		},
					    hasRadio: true,
	            		items:[
							{
								xtype: 'radiofield',
								margin: '4 0 0 0',
								width: 25,
								labelAlign: 'top',
								style: {
							    	padding:'3px'
					    		},
							},
							{
							    xtype: 'fieldcontainer',
							    layout: {
							        type: 'table',
							        columns: 11
							    },
							    defaults: {
							    	padding:'3px',
							    	margin: '5'
					    		},
					    		style: {
							    	'border-width': me.selectBorderWidth,
							    	'border-color': me.deselectBorderColor,
							    	'border-style': 'solid'
							    },
							    items: [
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{제안서제출 시작일시}',
							            readOnly: true,
							            itemId_t: 'specProposalBeginDateTime',
							            bind: {
							            	value : '{dateData.specProposalBeginDateTime}'
							            },
							            format: 'Y/m/d',
							            labelWidth: 170,
							            width: 270,
							            labelAlign: 'left',
							            name: 'startDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateHour',
                                        itemId_t: 'specProposalBeginDateHour',
                                        bind: {
                                            value: '{dateData.specProposalBeginDateHour}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateMinute',
                                        itemId_t: 'specProposalBeginDateMinute',
                                        bind: {
                                            value: '{dateData.specProposalBeginDateMinute}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: 0,
                                        text: me.minuteText
                                    },
							        {
                                        xtype: 'label',
                                        margin: '5',
                                        text: '~'
                                    },
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{제안서제출 마감일시}',
							            readOnly: true,
							            itemId_t: 'specProposalCloseDateTime',
							            bind: {
							            	value : '{dateData.specProposalCloseDateTime}'
							            },
							            format: 'Y/m/d',
							            labelWidth: 170,
							            width: 270,
							            labelAlign: 'left',
							            name: 'endDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'endDateHour',
                                        itemId_t: 'specProposalCloseDateHour',
                                        bind: {
                                            value: '{dateData.specProposalCloseDateHour}'
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'endDateMinute',
                                        itemId: 'specProposalCloseDateMinute',
                                        bind: {
                                            value: '{dateData.specProposalCloseDateMinute}'
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.minuteText
                                    }
							    ]
							}
	        			],
	        		},
	        		{
	            		xtype: 'container',
	            		layout: {
					        type: 'hbox',
					        align: 'stretch'
					    },
					    style: {
					    	padding:'5 5 5 5px'
			    		},
					    hasRadio: true,
	            		items:[
	            			{
	            				xtype: 'radiofield',
	            				margin: '4 0 0 0',
	            				width: 25,
	            				labelAlign: 'top',
            					style: {
            						padding:'3px'
            					}
	            			
	            			},
	            			{
							    xtype: 'fieldcontainer',
							    layout: {
							        type: 'table',
							        columns: 5
							    },
							    style: {
							    	'border-width': me.selectBorderWidth,
							    	'border-color': me.deselectBorderColor,
							    	'border-style': 'solid'
							    },
							    defaults: {
							    	padding:'3px',
							    	margin: '5'
					    		},
							    items: [
							        {
							            xtype: 'datefield',
							            fieldLabel: '#{개찰일시}',
							            readOnly: true,
							            itemId_t: 'openBidDateTime',
							            bind: {
							            	value: '{dateData.openBidDateTime}'
							            },
							            format: 'Y/m/d',
							            labelWidth: 170,
							            width: 270,
							            labelAlign: 'left',
							            name: 'startDate'
							        },
							        {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 24,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateHour',
                                        itemId: 'openBidDateHour',
                                        bind: {
                                            value: '{dateData.openBidDateHour}'
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: '0 2 0 0',
                                        text: me.hourText
                                    },
                                    {
                                        xtype: 'numberfield',
                                        margin: '0 2 0 0',
                                        width: 30,
                                        fieldLabel: '',
                                        emptyText: '0',
                                        decimalPrecision: 0,
                                        maxValue: 60,
                                        minValue: 0,
                                        readOnly: true,
                                        name: 'startDateMinute',
                                        itemId: 'openBidDateMinute',
                                        bind: {
                                            value: '{dateData.openBidDateMinute}',
                                        }
                                    },
                                    {
                                        xtype: 'label',
                                        margin: 0,
                                        text: me.minuteText
                                    }
							    ]
							}
	            		]
	            	}
			    ]
			},
			{
				xtype: 'container',
				reference: 'pickerContainer',
				margin: '5',
				layout: {
			        type: 'hbox',
			        align: 'stretch'
			    },
			    items: [
		            {
		            	xtype: 'panel',
		            	reference: 'startDatePanel',
		            	isPickerCt: true,
		            	title: me.startDatePickerTitle,
		            	flex:0.48,
		            	layout: {
					        type: 'hbox',
					        align: 'stretch'
					    },
		            	items: [
							{
								xtype: 'datepicker',
								reference: 'startDatePicker',
								flex: 0.6
							},
							{
								xtype: 'boundlist',
								reference: 'startHour',
								name: 'hour',
								flex: 0.2,
								height: 100,
								selModel: {
				                    mode: 'SINGLE',
				                    enableInitialSelection: false
				                },
				                style: {
				                	textAlign:'center'
				                },
				                preserveScrollOnRefresh: false,
				                displayField: 'text',
				                store: Ext.create('Ext.data.Store', {
				                	model: 'Ext.data.Model',
				                	data: me.getHour(1)
				                }),
				                listeners: {
				                	select: function(cmp, record, eOpts){
				                		var picker = this.picker,
				                			hourCmp = picker.ownerField.hourCmp;
				                		
				                		picker.ownerField.hourCmp.setValue(record.get('data'));
//				                		picker.fireEvent('afterpickerselect', {
//			                				'picker': picker,
//			                				'changedField':hourCmp
//		                				});
				                	}
				                }
							},
							{
								xtype: 'boundlist',
								reference: 'startMinute',
								name: 'minute',
								flex: 0.2,
								height: 100,
								selModel: {
				                    mode: 'SINGLE',
				                    enableInitialSelection: false
				                },
				                style: {
				                	textAlign:'center'
				                },
				                preserveScrollOnRefresh: false,
				                displayField: 'text',
				                store: Ext.create('Ext.data.Store', {
				                	model: 'Ext.data.Model',
				                	data: me.getMinute(1)
				                }),
				                listeners: {
				                	select: function(cmp, record, eOpts){
				                		var picker = this.picker,
				                			minuteCmp = picker.ownerField.minuteCmp;
				                		
				                		minuteCmp.setValue(record.get('data'));
//				                		picker.fireEvent('afterpickerselect', {
//			                				'picker': picker,
//			                				'changedField':minuteCmp
//		                				});
				                	}
				                }
							}
            	        ]
		            },
		            {
		            	xtype: 'container',
		            	flex: 0.04,
		            	layout: {
		            		type: 'vbox',
		            		pack: 'middle'
		            	},
		            	items:[{
	                        xtype: 'label',
	                        labelAlign: 'center',
	                        text: '~',
	                        style: {
	                        	marginLeft: '10px',
	                        	fontWeight: 'bold',
	                        	fontSize: '14px',
	                        	color: '#000'
	                        		
	                        }
	                    }]
		            },
		            {
		            	xtype: 'panel',
		            	reference: 'endDatePanel',
		            	isPickerCt: true,
		            	title: me.endDatePickerTitle,
		            	flex:0.48,
		            	layout: {
					        type: 'hbox',
					        align: 'stretch'
					    },
		            	items: [
							{
								xtype: 'datepicker',
								reference: 'endDatePicker',
								flex: 0.6
							},
							{
								xtype: 'boundlist',
								reference: 'endHour',
								name: 'hour',
								flex: 0.2,
								height: 100,
								selModel: {
				                    mode: 'SINGLE',
				                    enableInitialSelection: false
				                },
				                style: {
				                	textAlign:'center'
				                },
				                preserveScrollOnRefresh: false,
				                displayField: 'text',
				                store: Ext.create('Ext.data.Store', {
				                	model: 'Ext.data.Model',
				                	data: me.getHour(1)
				                }),
				                listeners: {
				                	select: function(cmp, record, eOpts){
				                		var picker = this.picker,
				                			hourCmp = picker.ownerField.hourCmp;
				                		
				                		hourCmp.setValue(record.get('data'));
//				                		picker.fireEvent('afterpickerselect', {
//			                				'picker': picker,
//			                				'changedField':hourCmp
//		                				});
				                	}
				                }
							},
							{
								xtype: 'boundlist',
								reference: 'endMinute',
								name: 'minute',
								flex: 0.2,
								height: 100,
								selModel: {
				                    mode: 'SINGLE',
				                    enableInitialSelection: false
				                },
				                style: {
				                	textAlign:'center'
				                },
				                preserveScrollOnRefresh: false,
				                displayField: 'text',
				                store: Ext.create('Ext.data.Store', {
				                	model: 'Ext.data.Model',
				                	data: me.getMinute(1)
				                }),
				                listeners: {
				                	select: function(cmp, record, eOpts){
				                		var picker = this.picker,
				                			minuteCmp = picker.ownerField.minuteCmp;
				                		
				                		minuteCmp.setValue(record.get('data'));
//			                			picker.fireEvent('afterpickerselect', {
//			                				'picker': picker,
//			                				'changedField':minuteCmp
//		                				});
				                	}
				                }
							}
            	        ]
		            }
			    ]
			}
        ];
    	me.callParent();
    	
    	me.on('afterrender', me.onAfterRender, me, {
    		single: true
    	});
    },
    
    onAfterRender: function(cmp){
    	var me = this,
    		containers = me.query('container[hasRadio=true]'),
    		radios = me.query('radiofield'),
    		datefields = me.query('datefield'),
    		datepickers = me.query('datepicker'),
    		headerCss = me.headerCSS;
    	
    	/** Init Component */
    	me.initDateField(datefields);
    	me.initDatePicker(datepickers);
    	me.initContainers(containers); // Picker Container ( not datefield container )
    	me.initRadioField(radios);
    	
    	/** Panel's Title CSS */
    	me.applyTitleCss(me.getHeader(), headerCss); // 메인 Title
    	me.applyTitleCss(me.startDatePanel, headerCss); // 시작일시 Title
    	me.applyTitleCss(me.endDatePanel, headerCss); // 마감일시 Title
    },
    
    /** Title CSS 적용 */
    applyTitleCss: function(panel, headerCss){
    	var _dom = panel.el.dom;
    	
    	for(var propertyName in headerCss){
    		_dom.querySelectorAll('.x-title-text')[0].style[propertyName] = headerCss[propertyName];
    	}
    },
    
    /** DateField 초기화 */
    initDateField: function(datefields){
    	var me = this;
    	Ext.each(datefields, function(field){
    		me.initDateValue(field);
    		me.hideDateField(field);
    		me.fieldKnowHourMinCmp(field);
    	});
    },
    
    /** DateField 오늘날짜로 초기화 */
    initDateValue: function(field){
    	field.setValue(new Date());
    },
    
    /** DatePicker의 컨테이너 초기화 */
    initContainers: function(containers){
    	var me = this;
    	Ext.each(containers, function(container){
    		/** 리스너 등록 */
    		container.on('checkchange', me.onCheckChangeContainer, me, {
    			'container': container
    		});
    	});
    },
    
    /** 라디오필드 초기화 */
    initRadioField: function(radios){
    	var me = this;
    	
    	Ext.each(radios, function(radio){
    		radio.inputEl.on('click', function(){
    			var me = this;
    			me.up('container[hasRadio=true]').fireEvent('checkchange');
    		}, radio);
    	});
    	
    	Etna.onDone(function(){
    		Ext.each(radios, function(radio){
    			if(radio.checked){
    				if(Ext.isIE){
    					/** 'IE'에서 inputEl.fireEvent('click')을 통해 등록한 리스너 'click' 미실행 */
    					radio.up('container[hasRadio=true]').fireEvent('checkchange');
    				}else{
    					radio.inputEl.fireEvent('click');
    				}
    			}
    		});
    	});
    },
    
    /** DatePicker 초기화 */
    initDatePicker: function(datepickers){
    	var me = this;
    	
    	me.registerPickerComponent();
    	
    	Ext.each(datepickers, function(picker){
    		var pickerPanel = picker.up('panel[isPickerCt=true]'),
    			boundLists = pickerPanel.query('boundlist');
    		
    		picker.on('select', me.onPickerSelect, me, {'picker':picker});
    		picker.on('afterpickerselect', me.onAfterPickerSelect, me, {'picker':picker});
    	});
    },
    
    /** Date, Hour, Minute 컴포넌트 등록 */
    registerPickerComponent: function(){
    	var me = this;
    	
    	/** 시작일시 컴포넌트 등록 */
		me.startDatePanel = me.lookupReference('startDatePanel'),
		me.startDatePicker = me.lookupReference('startDatePicker'),
		me.startHourCmp = me.lookupReference('startHour'),
		me.startMinuteCmp = me.lookupReference('startMinute'),
		
		/** 마감일시 컴포넌트 등록 */
		me.endDatePanel = me.lookupReference('endDatePanel');
		me.endDatePicker = me.lookupReference('endDatePicker'),
		me.endHourCmp = me.lookupReference('endHour'),
		me.endMinuteCmp = me.lookupReference('endMinute');
    },
    
    /** Hour, Minute 변경 시 dateManager에 접근하기 위해 picker(picker.dateManager)를 알고 있도록 함 */
    insertPickerIntoCmp: function(cmp, picker){
    	cmp.picker = picker;
    },
    
    /** DateField의 값을 DatePicker와 동기화 */
    connectFieldToPicker: function(container){
    	var me = this,
    		datefields = container.query('datefield'),
    		/** 시작일시 */
    		startDatePanel = me.startDatePanel,
    		startDatePicker = me.startDatePicker,
    		startHourCmp = me.startHourCmp,
    		startMinuteCmp = me.startMinuteCmp,
    		/** 마감일시 */
    		endDatePanel = me.endDatePanel;
    		endDatePicker = me.endDatePicker,
    		endHourCmp = me.endHourCmp,
    		endMinuteCmp = me.endMinuteCmp;
    	
    	/** 하단 시작일시, 마감일시 디폴트 셋팅 */
		startDatePanel.disable();
		startDatePanel.setTitle(me.startDatePickerTitle);
		endDatePanel.disable();
		endDatePanel.setTitle(me.endDatePickerTitle);
		
		/** Houre, Minute도 picker를 알 수 있도록 함 */
		me.insertPickerIntoCmp(startHourCmp, startDatePicker);
		me.insertPickerIntoCmp(startMinuteCmp, startDatePicker);
		me.insertPickerIntoCmp(endHourCmp, endDatePicker);
		me.insertPickerIntoCmp(endMinuteCmp, endDatePicker);

    	
    	Ext.each(datefields, function(field){
    		
    		if(field.name === 'startDate'){ 
    			
    			/** 시작일시 */
    			me.publishValueToPicker(
    					field, startDatePanel, startDatePicker, startHourCmp, startMinuteCmp);
    			/** 시,분 */
    			me.publishValueToHourMinCmp(field, startHourCmp, startMinuteCmp);
    			
    		}else if(field.name === 'endDate'){ 
    			
    			/** 마감일시 */
    			me.publishValueToPicker(
    					field, endDatePanel, endDatePicker, endHourCmp, endMinuteCmp);
    			/** 시,분 */
    			me.publishValueToHourMinCmp(field, endHourCmp, endMinuteCmp);
    		}
    	});
    },
    
    /** 상단 시,분을 하단의 시,분에 Value 전달 */
    publishValueToHourMinCmp: function(field, hourCmp, minuteCmp){
    	var me = this,
    		hour = field.hourCmp.getValue(), 
    		minute = field.minuteCmp.getValue();
		
		hour = hour ? hour : 0;
		minute = minute ? minute : 0;
		
		/** Value 선택 */
		me.selectHourMinValue(hourCmp, minuteCmp, hour, minute);
		
		/** Value에 맞추어, Scroll 이동 */
    	me.moveScrollY(minuteCmp, minute);
    	me.moveScrollY(hourCmp, hour);
    	
    	/** 하단 시,분 커포넌트 readOnly 속성 적용 */
    	me.selectHourMinConfig(hourCmp, field.hourCmp.nonSelect);
    	me.selectHourMinConfig(minuteCmp, field.minuteCmp.nonSelect);
    },
    
    /** datefield는 Hour, Minute 컴포넌트를 알고 있다 */
    fieldKnowHourMinCmp: function(field){
    	var me = this,
    		fieldContainer = field.up('fieldcontainer');
    	
    	if(field.name === 'startDate'){
    		field.hourCmp = fieldContainer.down('numberfield[name=startDateHour]');
    		field.minuteCmp = fieldContainer.down('numberfield[name=startDateMinute]');
    	}else if(field.name === 'endDate'){
    		field.hourCmp = fieldContainer.down('numberfield[name=endDateHour]');
    		field.minuteCmp = fieldContainer.down('numberfield[name=endDateMinute]');
    	}
    	
    	/** FieldContainer 리스너 등록 */
    	me.registerFieldListener(fieldContainer);
    },
    
    /** FieldContainer 'Click' 이벤트 리스너 등록 */
    registerFieldListener: function(fieldContainer){
    	var me = this;
    	
    	/** Click 이벤트 리스너 등록 */
    	fieldContainer.el.on('click', me.onFieldContainerClick, me, {
    		/** Param */'fieldContainer':fieldContainer
    	});
    },
    
    /** FieldContainer 'Click' 이벤트 핸들러 */
    onFieldContainerClick: function(event, targetEl, param, eOpts){
    	var me = this,
    		fieldContainer = param.fieldContainer;
    	
    	if(fieldContainer){
    		fieldContainer.up('container[hasRadio=true]').fireEvent('checkchange');
    	}
    },
    
    /** Picker에서 선택한 값을 datefield로 값 동기화(Hour, Minute은 제외) */
    onPickerSelect: function(picker){
    	var me = this,
    		field = picker.ownerField;
    	
    	field.setValue(picker.getValue());
    	
    	
    	// fireChangeEventFields
    	if(Ext.Array.contains(me.fireChangeEventFields, field.itemId_t)){
    		picker.fireEvent('afterpickerselect', {
    			'picker': picker,
    			'changedField':field
    		});
    	}
    },
    
    /** 라디오버튼 클릭 시, 컨테이너가 감지 */
    onCheckChangeContainer: function(param){
    	var me = this,
    		container = param.container,
    		startDatePanel = me.startDatePanel,
    		endDatePanel = me.endDatePanel;
    	
    	me.refreshRadios(container.down('radiofield'));
    	me.refreshFieldContainer(container.down('fieldcontainer'));
    	
    	Etna.onDone(function(){
    		startDatePanel.setLoading(true);
    		endDatePanel.setLoading(true);
    		Ext.defer(function(){
    			me.connectFieldToPicker(container);// datefield값을 picker로 전달
    			startDatePanel.setLoading(false);
    			endDatePanel.setLoading(false);
    		}, 100);
    	});
    },
    
    /** datefield의 값(date)을 DatePicker에 전달 */
    publishValueToPicker: function(field, datePanel, datePicker, hourCmp, minuteCmp){
    	datePanel.enable();
    	datePanel.setTitle(field.getFieldLabel());
    	datePicker.ownerField = field;
    	datePicker.setValue(field.getValue());
    	if(field.minValue){
    		datePicker.setMinDate(field.minValue);
    	}else{
    		datePicker.setMinDate(null);
    	}
    	
    	if(field.maxValue){
    		datePicker.setMaxDate(fielld.maxValue);
    	}else{
    		datePicker.setMaxDate(null);
    	}
    },
    
    /** datefield의 값(hour, min)을 각 Hour, Minute 컴포넌트에 전달 */
    selectHourMinValue: function(hourCmp, minuteCmp, hour, minute){
    	hourCmp.select(hour);
    	minuteCmp.select(minute);
    },
    
    /** 하단 시,분 컴포넌트 readOnly 속성 적용 */
    selectHourMinConfig: function(cmp, readOnly){
    	if(readOnly){
    		cmp.disable();
    		cmp.el.dom.style.pointerEvents = 'none';
    	}else{
    		cmp.enable();
    		cmp.el.dom.style.pointerEvents = 'auto';
    	}
    },
    
    /** Hour, Minute의 값 선택 후 선택된 값이 보이도록 Scroll 이동 */
    moveScrollY: function(cmp, term){
    	var me = this,
    		scrollYValue = me.moveScrollYSize*term;
    	
		cmp.setScrollY(scrollYValue);
    },
    
    /** Hour 컴포너넌트의 Store에 사용될 값 */
    getHour: function(period){
    	var me = this,
    		MAX_HOUR = 24,
    		hours = [];
    	
    	for(var i=0; i<MAX_HOUR; i++){
    		hours[i] = {
    				text:i+me.hourText,
    				data:i
			};
    	}
    	
    	return hours;
    },
    
    /** Minute 컴포넌트의 Store에 사용될 값 */
    getMinute: function(period){
    	var me = this,
			MAX_MINUTE = 60,
			minute = [];
	
		for(var i=0; (i*period)<MAX_MINUTE; i++){
			minute[i] = {
					text: (i*period)+me.minuteText,
					data: (i*period)
			};
		}
		
		return minute;
    },
    
    /** 우측 달력 아이콘 삭제 */
    hideDateField: function(field){
		field.triggerEl.elements[0].hide();
    },
    
    /** 라디오버튼의 체크박스 Refresh */
    refreshRadios: function(radio){
    	var me = this,
    		radios = me.query('radiofield');
    	
    	Ext.each(radios, function(_radio){
    		if(_radio !== radio){
    			_radio.setValue(false);
    		}else{
    			_radio.setValue(true);
    		}
    	});
    },
    
    /** 상단 datefield의 컨테이너로 선택 유무를 나타내기 위한 CSS 적용 */
    refreshFieldContainer: function(fieldContainer){
    	var me = this;
    		fieldContainers = me.query('fieldcontainer');
    		
    	Ext.each(fieldContainers, function(_fieldContainer){
    		var fieldContainerDom = _fieldContainer.getEl().dom;
    		if(_fieldContainer === fieldContainer){
    			fieldContainerDom.style.borderColor = me.selectBorderColor;
    		}else{
    			fieldContainerDom.style.borderColor = me.deselectBorderColor;
    		}
    	});
    },
    
    /** datefield의 value를 Picker value와 싱크 */
    syncPicker: function(){
    	var me = this,
    		form = me.lookupReference('kepcoDateForm'),
    		radios = form.query('radiofield');
    	
    	Ext.each(radios, function(radio){
    		if(radio.checked){
    			if(Ext.isIE){
    				radio.up('container[hasRadio=true]').fireEvent('checkchange');
    			}else{
    				radio.inputEl.fireEvent('click');
    			}
    		}
    	});
    },
    
    /**
     *  [화면 상황에 따라 아래 내용을 수정하시면 됩니다.]
     * 
     *  1. setComponentState:fn
     *    - 화면단의 컴포넌트 속성을 전달받아 상태값을 동기화 시키도록 합니다.
     *      컴포넌트의 itemId를 기준으로 맵핑하기 때문에 서로 itemId를 맞추어 주도록 합니다.
     *      그래서 화면의 itemId를 itemId_t에 동일하게 명시해야 합니다.
     *  
     *  2. setParameter:fn
     *    - 화면단에서 사용되고 있는 viewModel을 그대로 전달받아 Clone하여 사용합니다.
     *    
     *  3. applyDates:fn
     *    - 실제 적용여부를 판단하기 위한 펑션으로, 화면에 Validation 요청을 합니다.
     *      화면단에서는 'applydates'를 리스너로 등록하여 전달받은 파라미터값들이 유효한지 확인하도록 합니다.
     *      그리고 화면단에서 유효여부를 확인한 후, 'afterapplydates' 이벤트를 발생시켜 파라미터로 결과값을 리턴하도록 합니다.
     *  	파라미터는 {result:true,	message:'성공적으로 적용하였습니다.'} 또는 
     *              {result:false,	message:'유효하지 않은 값이 존재합니다.'}와 같은 형태로 보내면 됩니다.
     *  
     *  4. onAfterApplyDates:fn
     *    - 화면으로 부터 발생한 'afterapplydates' 이벤트를 받아서 처리합니다.
     *    
     *  5. onAfterPickerSelect:fn
     *    - DatePicker 클릭 시, 변경 이벤트 발생
     *    
     *  6. onEtnatogglefieldChange: fn
     *    - 토글 이벤트 핸들러
     *  
     * */
    
    /** 1. 필드 동적 처리 (실제화면의 컴포넌트 itemId와 맵핑) */
    setComponentState: function(datefields, numberfields, togglefield){
    	
    	var me = this;
    	for(var key in datefields){
    		/** 화면단에서 건네준 속성값을 맵핑. ( itemId to itemId_t ) */
    		var datefield = me.down('datefield[itemId_t='+key+']'),
    			config = datefields[key];
    		
    		if(datefield){
    			datefield.setFieldLabel(config.label);
    			
    			/** container[hasRadio=true]는 'datefield'와 'radiofield'의 컨테이너임을 의미함 */
    			datefield.up('container[hasRadio=true]').setVisible(config.visible);
    			datefield.setMinValue(config.minValue);
    			datefield.setMaxValue(config.maxValue);
    		}
    	}
    	
    	/** 시,분 속성값 맵핑 */
    	for(var key in numberfields){
    		var numberfield = me.down('numberfield[itemId_t='+key+']'),
    			config = numberfields[key];
    		
    		if(numberfield){
    			/** 시,분의 readOnly는 항상 true이므로, custom속성(selectable)에 담아둡니다 */
    			numberfield.nonSelect = config.readOnly;
    		}
    	}
    	
    	/** (Toggle) 상시투찰적용여부 */
    	var _togglefield = me.down('etnatogglefield[itemId_t=alwaysAttendYn]');
    	if(togglefield.readOnly){
    		_togglefield.disable();
    	}else{
    		_togglefield.enable();
    	}
    },
    
    /** 2. 파라미터 전달 */
    setParameter: function(param){
    	var me = this,
    		vm = me.getViewModel();

    	me.setLoading(true);
    	Ext.defer(function(){
    		Ext.suspendLayouts();
    		/** ViewModel Copy */
    		vm.set('dateData', param.copy(null));
    		Etna.onDone(function(){
    			Ext.resumeLayouts(true);
    			me.setLoading(false);
    		});
    	}, 10);
    },
    
    /** 3. '적용'버튼 클릭. datefield의 값 validation 체크 */
    applyDates: function(){
    	var me = this,
    		vm = me.getViewModel(),
    		/** ViewModel Copy */
    		dateDataClone = vm.get('dateData').copy(null);
    	
    	me.setLoading(true);
    	Ext.defer(function(){
    		me.on('afterapplydates', me.onAfterApplyDates, me, {
    			single: true
    		});
    		me.fireEvent('applydates', dateDataClone);
    	}, 10);
    },
    
    /** 4. [Event] validation 결과값에 따라서 창을 닫을지 메시지를 보여줄지 결정 */
    onAfterApplyDates: function(result, eOpts){
    	var me = this;
    	me.setLoading(false);
    	if(result.result){
    		me.close();
    	}
    	Etna.Message.alert(result.message);
    },
    
    /** DatePicker/Hour/Minute After Select Event */
    onAfterPickerSelect: function(param){
    	
    	var me = this,
    		vm = me.getViewModel(), // vm.get('dateData')
    		dateData = vm.get('dateData'),
    		picker = param.picker,
    		changedField = param.changedField, // 변경된 필드
    		changedFieldId = changedField.itemId_t, // 변경된 필드명
    		datefield = picker.ownerField,
    		hourCmp = datefield.hourCmp,
    		minuteCmp = datefield.minuteCmp;
    	
    	me.fireEvent('afterpickerchange', {
			'dateDate':dateData.copy(null),
			'changedFieldId':changedFieldId
    	});
    },
    
    /** 토글 핸들러 */
    onEtnatogglefieldChange: function(field, newValue, oldValue, eOpts) {
    	var me = this,
    		vm = me.getViewModel();
    	
    	var form = me.lookupReference('kepcoDateForm');
    	
    	// 입찰서제출 시작일시
        var beginDateTimeField = form.down('datefield[itemId_t=beginDateTime]'),
        	beginDateTimeFieldCt = beginDateTimeField.up('container[hasRadio=true]');
        
        // 제안서제출 시작일시. datefield.up('container[hasRadio=true]')
        var specProposalBeginDateField = form.down('datefield[itemId_t=specProposalBeginDateTime]'),
        	specProposalBeginDateFieldCt = specProposalBeginDateField.up('container[hasRadio=true]');

        if(newValue == true){	// 상시투찰 : 적용, 수정가능.
            if(vm.get('dateData.bidAttendRequestBeginDateTime')){
                if(beginDateTimeFieldCt.isVisible() && vm.get('dateData.beginDateTime')){	// 입찰서 시작일시 case
                    vm.set('dateData.beginDateTime', vm.get('dateData.bidAttendRequestBeginDateTime'));
                    vm.set('dateData.beginDateHour', vm.get('dateData.bidAttendRequestBeginDateHour'));
                    vm.set('dateData.beginDateMinute', vm.get('dateData.bidAttendRequestBeginDateMinute'));
                }else if(specProposalBeginDateFieldCt.isVisible() && vm.get('dateData.specProposalBeginDateTime')){	// 제안,규격 시작일시 case
                    vm.set('dateData.specProposalBeginDateTime', vm.get('dateData.bidAttendRequestBeginDateTime'));
                    vm.set('dateData.specProposalBeginDateHour', vm.get('dateData.bidAttendRequestBeginDateHour'));
                    vm.set('dateData.specProposalBeginDateMinute', vm.get('dateData.bidAttendRequestBeginDateMinute'));
                }
            }
        }
    }
});