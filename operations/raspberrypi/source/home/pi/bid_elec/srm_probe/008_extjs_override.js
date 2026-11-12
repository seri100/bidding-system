/********** 2025.02.26 고아라 *********/
/** 메시지 기록 페이지 노출 취약점 조치(로컬 스토리지 다국어 메시지 적재 기능 비활성화) */
// 특정 Flag 값 체크하여, 다국어 메시지 모두 제거
// 개인화 데이터는 제거 대상이 아니기 때문에, Key값(i18n-) 확인하여 제거
(function(){
 var storageClearDelimeter = "extjs.i18n.clear", // 삭제 기준 키워드
		clearDate = "2025-02-11"; // 삭제 기준 날짜 (삭제된 날짜를 알기 위함이 목적)
//	if (localStorage.getItem(storageClearDelimeter)) {
//		return;
//	}	
	var keys = Object.keys(localStorage);
	for (var i = 0, key; i < keys.length ; i++) {
		key = keys[i];
		if (key.indexOf('i18n-') == 0) {
			localStorage.removeItem(key);
		}
	}
	localStorage.setItem(storageClearDelimeter, new Date(clearDate).getTime());
}());
//-------------------------------------------------------
//CSRF 관련 부분
//-------------------------------------------------------
if (Ext.query("meta[name='_csrf']").length
		&& Ext.query("meta[name='_csrf_header']").length
		&& Ext.query("meta[name='_csrf_parameter']").length) {
	// ajax
	var _csrfHeaders = {};
	_csrfHeaders[Ext.query("meta[name='_csrf_header']")[0].content] = Ext
	.query("meta[name='_csrf']")[0].content;

	var params = {};
	params[Ext.query("meta[name='_csrf_parameter']")[0].content] = Ext
	.query("meta[name='_csrf']")[0].content;



	/** [2016.10.07] 파일서버 분리 작업.
	 *  noneFileServer:true => 파일서버 분리 사용안함
	 *  noneFileServer:false => 파일서버 분리 사용함
	 */
	var noneFileServer = true;
	
	if(noneFileServer){	/** 파일서버 사용 안함 */
		Ext.Function.interceptBefore(Ext.Ajax, "request", function(options) {
			options.headers = Ext.apply(options.headers || {}, _csrfHeaders)
		});
		// upload 부분(차후 변경 될 수 있음/차후에도 기능은 동작)
		Ext.define('Csrf.Etna.upload.StoreBasedUploader', {
			override : 'Etna.upload.StoreBasedUploader',
	
			onPluploadBeforeUpload : function(uploader, file) {
				Ext.apply(uploader.settings.headers, _csrfHeaders);
				this.callParent(arguments);
			}
		});
		
	}else{	/** 파일서버 사용함 */
/**
		var	fileServerUrl = 'http://cfile.kepco.net:8080/kepcoFile/', // 파일서버 도메인
		
		 */
		var	fileServerUrl = '', // 파일서버 도메인 존재하지 않음 noneFileServer는 항상 true로 확인 웹 취약점 관련 조치 사항 김형민
			attachmentUrls = [ // 첨부파일 Method 리스트 (/router)
				'getAttachments',	// 조회
				'removeAttachment',	// 수정
				'updateAttachment'	// 삭제
			];
		Ext.Function.interceptBefore(Ext.Ajax, "request", function(options) {
			var isFile = false;
			var realCsrfToken = _csrfHeaders['X-CSRF-TOKEN'];
			
			if(options.jsonData){
				if(options.jsonData.action){
					if(options.jsonData.action.indexOf('smartsuit.ui.etnajs.cmmn.CommonController') > -1){
						var _method = options.jsonData.method;
						Ext.each(attachmentUrls, function(url){
							if(_method.indexOf(url) >= 0){
								isFile=true;
							} 
						}); // end each
					} 
				} // end if(options.jsonData.action)
				
				if(isFile){
				
					var usertoken = "";
					
					/** 파일서버에 인증 요청할 토큰값을 가져옴 */
					Ext.Ajax.request({
						url:'getUserToken.do',
						async : false,
						success:function(result,request){
							usertoken = result.responseText;
						}
					});
					
					/** CORS(Cross Origin Resource Sharing)추가에 따른 Ext.Ajax.request 속성 추가 */
					Ext.Ajax.request({ 
						url: fileServerUrl+'kepcoFileServerCheck.do',
						method: 'POST',
						async : false,
						cors: true,					// CORS
						withCredentials: true,		// CORS(쿠키값 전달)
						useDefaultXhrHeader: false,	// CORS
						success:function(result,request){
							/** 파일서버 요청에 사용 될 CSRF Token */
							_csrfHeaders['X-CSRF-TOKEN'] = result.getResponseHeader("x-csrf-token");
						}
					});
					
					/** 파일서버 인증 진행 */
					Ext.Ajax.request({
						url:fileServerUrl+'kepcoFileServerLoginCheck.do',
						method: 'POST',
						async : false,
						cors: true,
						withCredentials: true,
						useDefaultXhrHeader: false,
						params:{token:usertoken},
						success:function(result,request){
							options.url = fileServerUrl+"router";
						}
					});
				}
			}
			
			options.headers = Ext.apply(options.headers || {}, _csrfHeaders);
			_csrfHeaders['X-CSRF-TOKEN'] = realCsrfToken;
		});
		
		Ext.define('Cmmn.override.upload.StoreBasedUploader', {
			override: 'Etna.upload.StoreBasedUploader',
			uploadUrl: fileServerUrl+'uploadAttachment.do',
		    downloadUrl: fileServerUrl+'downloadAttachment.do',
			
			initComponent: function(){
				var me = this;
				
				me.setReference(me.getReference()+'_storebaseduploader');
				me.callParent(arguments);
			},
			
			/** 쿠키값을 전달을 위한, 오버라이드 */
			initPlUpload: function(initializer) {
		        var me = this,
		            initializer = initializer || function(fn, scope) {
		                fn.call(scope);
		                Ext.Logger.log(me.id + ' plupload init function called');
		            },
		            uploader = new plupload.Uploader({
		                uploader: me,
		                url: me.uploadUrl,
		                headers: me.getMultipartHeaders(),
		                filters: me.getPluploadFilter(),
		                runtimes: me.pluploadRuntimes,
		                flash_swf_url: me.flashSwfUrl,
		                silverlight_xap_url: me.silverlightXapUrl,
		                browse_button: me.getBrowseButtonId(),
		                drop_element: me.getDropElementId(),
		                multi_selection: me.getMultiSelection(),
		                required_features: 'send_browser_cookies',	// 쿠키값 전달 속성(세션값 공유를 위함)
		                multipart: true
		            });
		        delete me.initialized;
		        Ext.Array.each([
		            'Init',
		            'PostInit',
		            'FilesAdded',
		            'QueueChanged',
		            'FilesRemoved',
		            'FileUploaded',
		            'BeforeUpload',
		            'StateChanged',
		            'UploadProgress',
		            'Error',
		            'Destroy'
		        ], function(v) {
		            uploader.bind(v, Ext.Function.alias(me, 'onPlupload' + v), me);
		        }, me);
		        me.setUploader(uploader);
		        initializer(uploader.init, uploader);
		    }
		});
		
		/** 파일 업로드 시, CSRF 토큰 추가 */
		Ext.define('Csrf.Etna.upload.StoreBasedUploader', {
			override : 'Etna.upload.StoreBasedUploader',
			isLoading : false,
			prevCsrfToken : '',
			onPluploadBeforeUpload : function(uploader, file) {
				var _csrfFileHeaders = {}, me = this;
				
				if(me.endUploadId){
					console.log('remove endUpload Object');
					clearTimeout(me.endUploadId);
					delete me.endUploadId;
				}
				
				if(me.isLoading){
					// 업로드 진행중
					_csrfFileHeaders['X-CSRF-TOKEN'] = me.prevCsrfToken;
				}else{
					me.isLoading = true;
					Ext.Ajax.request({
						method: 'POST',
						url:fileServerUrl+'kepcoFileServerCheck.do',
						async : false,
						cors: true,
						withCredentials: true,
						useDefaultXhrHeader: false,
						success:function(result,request){
							me.prevCsrfToken = _csrfFileHeaders['X-CSRF-TOKEN'] 
											 = result.getResponseHeader('x-csrf-token');
						}
					});
				}
				
				// 파일 업로드 시, 파일서버 CSRF 토큰 추가
				Ext.apply(uploader.settings.headers, _csrfFileHeaders);
				this.callParent(arguments);
			},
			/** 업로드 완료 시점 */
			onPluploadFileUploaded : function(uploader, file, status){
				var me = this;
				
				me.callParent(arguments);
				me.endUploadId = setTimeout(function(){
					me.isLoading = false;
					delete me.endUploadId;
				}, 1000);
			}
		});
		
		/** CORS 적용을 위해 오버라이드 */
		Ext.define('Site.direct.RemotingProvider', {
			override : 'Ext.direct.RemotingProvider',
			
			queueTransaction: function(transaction) {
				var me = this, isFile = false,
				enableBuffer = me.enableBuffer;
				  
				if (transaction.form) {
					me.sendFormRequest(transaction);
					return;
				}
				
				if (enableBuffer === false || typeof transaction.timeout !== 'undefined') {
					me.sendRequest(transaction);
					return;
				}
				
				if(transaction.action === "smartsuit.ui.etnajs.cmmn.CommonController"){
					var _method = transaction.method;
					if(_method){
						Ext.each(attachmentUrls, function(url){
							if(_method.indexOf(url) >= 0){
								isFile = true;
							}
						});
					}
				}
				
				if(isFile){
					/** 단일 요청 */
					me.sendRequest(transaction);
				}else{
					me.callBuffer.push(transaction);
				}
				
				if (enableBuffer) {
					if (!me.callTask) {
						me.callTask = new Ext.util.DelayedTask(me.combineAndSend, me);
					}
					me.callTask.delay(Ext.isNumber(enableBuffer) ? enableBuffer : 10);
				}
				else {
					me.combineAndSend();
				}
			},
		    sendRequest: function(data) {
		        var me = this,
		            request, callData, params,
		            enableUrlEncode = me.enableUrlEncode,
		            i, len;
		
				request = {
		            url: me.url,
		            callback: me.onData,
		            scope: me,
		            transaction: data,
		            timeout: me.timeout
		        };
		        
		        if(data.method){
		        	var _method = data.method;
		        	Ext.each(attachmentUrls, function(url){
						if(_method.indexOf(url) >= 0){
							/** CORS적용 */
							request.async = false;
							request.useDefaultXhrHeader = false;
							request.cors = true;
							request.withCredentials = true;
						}
					});
		        }
		        
		        if (data.timeout) {
		            request.timeout = data.timeout;
		        }
		
		        if (Ext.isArray(data)) {
		            callData = [];
		
		            for (i = 0, len = data.length; i < len; ++i) {
		                callData.push(me.getCallData(data[i]));
		            }
		        }
		        else {
		            callData = me.getCallData(data);
		        }
		
		        if (enableUrlEncode) {
		            params = {};
		            params[Ext.isString(enableUrlEncode) ? enableUrlEncode : 'data'] = Ext.encode(callData);
		            request.params = params;
		        }
		        else {
		            request.jsonData = callData;
		        }
		        Ext.Ajax.request(request);
		    }
		});
		
		/** Requset의 Contnent-Type헤더 제거를 위해 오버라이드 */
		Ext.define('Etna.override.data.Connection', {
		    override: 'Ext.data.Connection',
		    setupHeaders: function(xhr, options, data, params) {
		        var me = this,
		            headers = Ext.apply({}, options.headers || {}, me.getDefaultHeaders() || {}),
		            contentType = me.getDefaultPostHeader(),
		            jsonData = options.jsonData,
		            xmlData = options.xmlData,
		            type = 'Content-Type',
		            useHeader = Ext.isDefined(options.useDefaultXhrHeader) ? options.useDefaultXhrHeader : me.getUseDefaultXhrHeader(),
		            key,
		            header;
		
		        if (!headers.hasOwnProperty(type) && (data || params)) {
		            if (data) {
		                if (options.rawData) {
		                    contentType = 'text/plain';
		                } else {
		                    if (xmlData && Ext.isDefined(xmlData)) {
		                        contentType = 'text/xml';
		                    } else if (jsonData && Ext.isDefined(jsonData)) {
		                        contentType = 'application/json';
		                    }
		                }
		            }
		            headers[type] = contentType;
		        }
		
		        if (useHeader && !headers['X-Requested-With']) {
		            headers['X-Requested-With'] = me.getDefaultXhrHeader();
		        }
		
		        
		        
		        if (headers[type] === undefined || headers[type] === null) {
		            delete headers[type];
		        }
		
				/** Content-Type 삭제 (IE에서 커스텀 헤더값을 하나만 허용하므로,
			     *	X-CSRF-TOKEN외의 헤더는 모두 제거)
			 	 */
				if( jsonData && jsonData.method){
					var _method = jsonData.method;
					Ext.each(attachmentUrls, function(url){
						if(_method.indexOf(url) >= 0){
							delete headers['Content-Type'];
						}
					});
				}
		        
		        try {
		            for (key in headers) {
		                if (headers.hasOwnProperty(key)) {
		                    header = headers[key];
		                    xhr.setRequestHeader(key, header);
		                }
		            }
		        } catch(e) {
		            me.fireEvent('exception', key, header);
		        }
		        return headers;
		    }
		});
	}
	
	// 엑셀 업로드
	Ext.define('Csrf.Etna.grid.plugin.ui.Import', {
		override : 'Etna.grid.plugin.ui.Import',
		onPluploadBeforeUpload : function(uploader, file) {
			Ext.apply(uploader.settings.headers, _csrfHeaders);
			this.callParent(arguments);
		},
		
		
		headerFieldLabel : '#{시작행}',
		fileNameFieldLabel : '#{파일명}',
		removeBlankRowLabel : '#{빈 행 무시}',
		applyText : '#{적용}',
		
		initComponent : function() {
			var me = this,
				importer = me.getImporter();
			Ext.apply(me, {
				items : me.createGridPanel(),
				dockedItems : [{
					dock : 'top',
					xtype : 'toolbar',
					itemId : 'import-browse-toolbar',
					items : [{
						xtype : 'numberfield',
						fieldLabel : me.headerFieldLabel,
						itemId : 'headerRowField',
						value : importer.headerRowCount,
						readOnly : importer.enforceHeaderRowCount,
						maxValue : 99,
						minValue : 0,
						listeners : {
							change : function(field, value) {
								if(field.initialValue) {
									delete field.initialValue;
									return;
								}
								me.headerCountTask.cancel();
								me.headerCountTask.delay(500, null, null, [value]);
							}
						}
					}, '->', {
						xtype : 'displayfield',
						itemId : 'fileName',
						fieldLabel : me.fileNameFieldLabel,
						labelWidth : 80,
						flex : 1
					}, {
						xtype : 'button',
						itemId : 'browseButton',
						iconCls : 'import-browse-icon',
						text : '#{파일첨부}',
						disabled : true
					}]
				}, {
					dock : 'top',
					xtype : 'toolbar',
					itemId : 'import-apply-toolbar',
					border : true,
					items : ['->', {
						xtype : 'checkbox',
						boxLabel : me.removeBlankRowLabel,
						checked : me.eliminatedBlankRow,
						header : {
							sortable : false
						},
						listeners : {
							change : function(field, newValue, oldValue) {
								me.eliminatedBlankRow = newValue;
								me.getImporter().parse(me.data);
							}
						}
					}, {
						xtype : 'button',
						itemId : 'applyButton',
						text : me.applyText,
						disabled : true,
						handler : function() {
							me.getImporter().migration();
						}
					}]
				}],
				bbar : {
					itemId : 'import-bbar',
					hidden : true,
					items : [new Ext.ProgressBar({
						animate : true,
						itemId : 'importProgressBar',
						flex : 1
					})]
				},
				listeners : {
					initialized : function() {
						me.getBrowseButton().setDisabled(false);
					},
					scope : me
				}
			});
			me.preInitPlUpload();
			me.callSuper(arguments);
			me.setGrid(me.down('panel'));
		},

	});
	// 엑셀 다운로드
	Ext.define('Csrf.Etna.grid.plugin.Export', {
		override : 'Etna.grid.plugin.Export',
		config : {
			params : Ext.clone(params)
		}
	});
}

//-------------------------------------------------------
//파일 업로드 관련 부분
//-------------------------------------------------------
//파일 업로드   용량 개당 50 총 100m 로 정의 20160527  자재처와 협의사항
//[2017.06.01 조은애] 100 -> 200mb 변경 이파피루스 도입 후 100mb로 변경 필요
//[2021.10.05 김재연] 개별 최대 파일 사이즈 변경 50m -> 100m (자재처 조현익 대리 요청)
Ext.define('Site.override.upload.StoreBasedUploader',{
	override : 'Etna.upload.StoreBasedUploader',
	config : {
		maxFileSize: '100m',
		totalFileSize : '500m' 
	},
	filters : {
		mime_types : 
			[
			 { title : "Image files", extensions : "jpeg,jpg,gif,png,tif,bmp" },
			 { title : "Zip files", extensions : "zip" },
			 { title : "Document files", extensions : "txt,xls,doc,ppt,xlsx,docx,pptx,rtf,gul,hwp,pdf,mht,eml,bid,wbid,obid,hwpx"}
			 ]
	}
});
//엑셀 업로드
Ext.define('Site.override.grid.plugin.ui.Import',{
	override : 'Etna.grid.plugin.ui.Import',
	maxFileSize: '10m',
	filters : {
		mime_types : 
			[
			 { title : "Excel files", extensions : "xlsx"}
			 ]
	}
//filters : {
//mime_types : 
//[
//{ title : "Image files", extensions : "jpg,gif,png,tif,bmp" },
//{ title : "Zip files", extensions : "zip" },
//{ title : "Document files", extensions : "txt,xls,doc,ppt,xlsx,docx,pptx,rtf,gul,hwp,pdf,mht,eml"}
//]
//}
});

//오류 메세지 override
Ext.define('Site.override.ServerExceptionHandler', {
	override : 'Cmmn.ServerExceptionHandler',
	defaultExceptionsHandler : function(exceptions){
		var expired = Ext.util.Cookies.get('session-expired');
		var loginIp = Ext.util.Cookies.get('duplicate.ip');
		if(! (expired || loginIp)){
			Ext.Msg.show({
				title: Ext.String.format('#{오류}'),
				message: Ext.String.format('#{{0} 개의 오류가 발생하였습니다.}', exceptions.length),
				buttons: Ext.Msg.OK,
				icon: Ext.Msg.ERROR
			});
		}
	},
	goToLogin : function(){
		try{
			if(parent != window){
				parent.Cmmn.ServerExceptionHandler.goToLogin();
			}else{
				location.href='index.do';
			}
		}catch(e){
			location.href='index.do';
		}
	},
    accessDeniedExceptionsHandler: function(exceptions) {
        var me = this;
        Ext.Msg.alert(me.warnMessage, me.accessDeniedMessage, function(btn) {
        	if(beforeUnloadHandler){
        		Ext.getWin().un('beforeunload', beforeUnloadHandler);
        	}
            me.goToLogin();
        });
    }
});

Ext.define('Site.override.SessionExpiredCheck', {
	warnMessage : 'Warn',
	expiredMessage : 'Session Expired.',
	duplicateMessage : 'Session Expired by Duplicated Login.',

	constructor : function(){
		var me = this;
		Ext.defer(function(){
			me.warnMessage = Ext.String.format('#{Warn}');
			me.expiredMessage = Ext.String.format('#{session.expired}');
			me.duplicateMessage = Ext.String.format('#{IP : [ip]<br>로그인 시간 : [time]<br><br>현재 중복 로그인 되어 자동으로 로그아웃 됩니다.}');
		}, 1000);
	},
	init : function(){
		var me = this;
		var sessionExpiredCheckerId = Ext.interval(function(){
			var expired = Ext.util.Cookies.get('session-expired');
			var loginIp = Ext.util.Cookies.get('duplicate.ip');
			var loginTime = Ext.util.Cookies.get('duplicate.logintime');

			if(expired || loginIp){
				clearInterval(sessionExpiredCheckerId);
				if(loginIp){
					me.duplicateSessionMessage(loginIp, loginTime);
				}else{
					me.expiredSessionMessage();
				}
			}
		}, 2000);
	},
	expiredSessionMessage : function(){
		Ext.create('Ext.window.MessageBox', {
			alwaysOnTop : true
		}).show({
			title: this.warnMessage,
			message: this.expiredMessage,
			buttons: Ext.Msg.OK,
			icon: Ext.Msg.WARN,
			closable:false,
			fn : this.expiredResult
		});
	},
	duplicateSessionMessage : function(loginIp, loginTime){
		loginTime = loginTime.split('"').join('');
		Ext.create('Ext.window.MessageBox', {
			alwaysOnTop : true
		}).show({
			title: this.warnMessage,
			message: this.duplicateMessage.replace('[ip]', loginIp).replace('[time]', loginTime),
			buttons: Ext.Msg.OK,
			icon: Ext.Msg.WARN,
			closable:false,
			fn : this.expiredResult
		});
	},
	expiredResult : function(button){

		Ext.util.Cookies.clear('session-expired');
		Ext.util.Cookies.clear('duplicate.ip');
		Ext.util.Cookies.clear('duplicate.logintime');

		if(button === 'ok'){
			if(beforeUnloadHandler){
				Ext.getWin().un('beforeunload', beforeUnloadHandler);
			}
			Cmmn.ServerExceptionHandler.goToLogin();
		}
	}
});

//엑셀 다운로드 - 렌더링 사용 check && RNDETNA-592 Export 기능개선
Ext.define('Cmmn.override.grid.plugin.Export', {
	override: 'Etna.grid.plugin.Export',
	defaultRenderedValue: true
});

//첨부필드 그리드로 먼저 보이도록 적용
Ext.define('Cmmn.override.form.field.Attachment', {
	override : 'Etna.upload.StoreBasedUploader',
	activeItem: 1
});

//그리드 세로줄 적용
Ext.define('Cmmn.override.grid.Panel', {
	override: 'Ext.grid.Panel',
	columnLines: true,
	enableColumnHide : false
});
//전화번호 -문자로 구분
Ext.define('Site.util.Format', {
	singleton : true,
	gridPhone : function(value, format) {

		var phoneNumberRe = /[0-9]{2,3}-[0-9]{3,4}-[0-9]{4}/,
		phoneNumber = [],
		t = value,
		first,
		last,
		retVal;

		if(Ext.isEmpty(value)) {
			return value;
		}

		first = Ext.String.startsWith(t, '02') ? 2 : 3;
		phoneNumber.push(t.substr(0, first));
		t = t.substr(first);
		last = t.length - 4;
		phoneNumber.push(t.substr(0, last));
		phoneNumber.push(t.substr(last));
		retVal = phoneNumber.join('-');

		if(phoneNumberRe.test(retVal)) {
			if(format) {
				retVal = Ext.String.format.apply(null, Ext.Array.insert(phoneNumber, 0, [format]));
			}
			return retVal;
		}
		return value;
	},
	phone : function(field, format) {

		var phoneNumberRe = /[0-9]{2,3}-[0-9]{3,4}-[0-9]{4}/,
		phoneNumber = [],
		t = field.getValue(),
		first,
		last,
		retVal;

		if(Ext.isEmpty(field.getValue())) {
			return field.getValue();
		} else if(/[^0-9]/g.test(field.getValue())) {
			field.setValue('');
		}

		first = Ext.String.startsWith(t, '02') ? 2 : 3;
		if(first == 2){
			if(field.getValue().length > 10){
				t = field.getValue().substr(0,10);
				field.setValue(t);	
			}
		}
		phoneNumber.push(t.substr(0, first));
		t = t.substr(first);
		last = t.length - 4;
		phoneNumber.push(t.substr(0, last));
		phoneNumber.push(t.substr(last));
		retVal = phoneNumber.join('-');
		if(first == 2) field.maxLength =10;
		else field.maxLength = 11;
		field.enforceMaxLength=true;

		if(phoneNumberRe.test(retVal)) {
			if(format) {
				retVal = Ext.String.format.apply(null, Ext.Array.insert(phoneNumber, 0, [format]));
			}
			return retVal;
		}
		return field.getValue();
	},
	//사업자번호 포맷
	BRNumber : function(field, format){
		var businessRegistrationNumRe = /[0-9]{3}-[0-9]{2}-[0-9]{5}/,
		businessRegistrationNum = [],
		t = field.getValue(),
		retVal;

		if(Ext.isEmpty(field.getValue())) {
			return field.getValue();
		} else if(/[^0-9]/g.test(field.getValue())) {
			field.setValue('');
		}
		businessRegistrationNum.push(t.substr(0, 3));
		businessRegistrationNum.push(t.substr(3, 2));
		businessRegistrationNum.push(t.substr(5));
		retVal = businessRegistrationNum.join('-');

		if(businessRegistrationNumRe.test(retVal)) {
			if(format) {
				retVal = Ext.String.format.apply(null, Ext.Array.insert(businessRegistrationNum, 0, [format]));
			}
			return retVal;
		}
		return field.getValue();
	},
	//사업자번호 포맷(그리드)
	gridBRNumber : function(value, format) {

		var businessRegistrationNumRe = /[0-9]{3}-[0-9]{2}-[0-9]{5}/,
		businessRegistrationNum = [],
		t = value,
		retVal;

		if(Ext.isEmpty(value)) {
			return value;
		}

		businessRegistrationNum.push(t.substr(0, 3));
		businessRegistrationNum.push(t.substr(3, 2));
		businessRegistrationNum.push(t.substr(5));
		retVal = businessRegistrationNum.join('-');


		if(businessRegistrationNumRe.test(retVal)) {
			if(format) {
				retVal = Ext.String.format.apply(null, Ext.Array.insert(businessRegistrationNum, 0, [format]));
			}
			return retVal;
		}
		return value;
	},
	gridMaskBRNumber : function(value, format) {

		var businessRegistrationNumRe = /[0-9]{3}-[*]{2}-[*]{5}/,
		businessRegistrationNum = [],
		t = value,
		retVal;

		if(Ext.isEmpty(value)) {
			return value;
		}

		businessRegistrationNum.push(t.substr(0, 3));
		businessRegistrationNum.push('**');
		businessRegistrationNum.push('*****');
		retVal = businessRegistrationNum.join('-');


		if(businessRegistrationNumRe.test(retVal)) {
			if(format) {
				retVal = Ext.String.format.apply(null, Ext.Array.insert(businessRegistrationNum, 0, [format]));
			}
			return retVal;
		}
		return value;
	},
	MaskBRNumber : function(field, format){
		var businessRegistrationNumRe = /[0-9]{3}-[*]{2}-[*]{5}/,
		businessRegistrationNum = [],
		t = field.getValue(),
		retVal;

		if(Ext.isEmpty(field.getValue())) {
			return field.getValue();
		} else if(/[^0-9]/g.test(field.getValue())) {
			field.setValue('');
		}
		businessRegistrationNum.push(t.substr(0, 3));
		businessRegistrationNum.push('**');
		businessRegistrationNum.push('*****');
		retVal = businessRegistrationNum.join('-');

		if(businessRegistrationNumRe.test(retVal)) {
			if(format) {
				retVal = Ext.String.format.apply(null, Ext.Array.insert(businessRegistrationNum, 0, [format]));
			}
			return retVal;
		}
		return field.getValue();
	},

	//년월포멧 (그리드)
	gridYearAndMonth : function(value, format) {
		var yearAndMonthNumRe = /[0-9]{4}-[0-9]{2}/,
		yearAndMonthNum = [],
		t = value,
		retVal;

		if(Ext.isEmpty(value)) {
			return value;
		}

		yearAndMonthNum.push(t.substr(0, 4));
		yearAndMonthNum.push(t.substr(4, 2));
		retVal = yearAndMonthNum.join('-');


		if(yearAndMonthNumRe.test(retVal)) {
			if(format) {
				retVal = Ext.String.format.apply(null, Ext.Array.insert(yearAndMonthNum, 0, [format]));
			}
			return retVal;
		}
		return value;
	},

	//동적 form 만들기
	makeForm: function(action,method,target){

		var frm = document.createElement('form');
		frm.setAttribute("action", action);
		frm.setAttribute("method", method);
		frm.setAttribute("target", target);
		return frm;
	},
	
	//동적 Input 만들기
	 makeInput: function(type, name, value) {
         var field = document.createElement('input');
         field.setAttribute("type", type);
         field.setAttribute("name", name);
         field.setAttribute("value", value);
         return field;
	 },
	
	// 금액(소수점) 한글변환
	 decimalNumberWord: function(amount, currencyCode, purchaseType) {
        var strAmount = amount.toString();
        var currencyCodeKor = null;
        var postCurrencyCodeKor = null;
        
        if(purchaseType === 'ConstructionService'){	// 공사용역
        	if(currencyCode === 'KRW'){
                currencyCodeKor = Ext.String.format('#{원}');
            }else if(currencyCode === 'USD'){
           	 	currencyCodeKor = Ext.String.format('#{달러}');
            }else if(currencyCode === 'KRD'){
            	amount = amount * 1000;
            	currencyCodeKor = Ext.String.format('#{원}');
            }
        	
        	return Ext.String.format('#{{0} {1}}', Ext.util.Format.numberWord(amount), currencyCodeKor);
        	
        }else{	// 자재
        	if(currencyCode === 'KRW'){
                postCurrencyCodeKor = Ext.String.format('#{전}');
                currencyCodeKor = Ext.String.format('#{원}');
            }else if(currencyCode === 'USD'){
           	 postCurrencyCodeKor = Ext.String.format('#{센트}');
           	 currencyCodeKor = Ext.String.format('#{달러}');
            }
            
            if(amount > 0 && strAmount.indexOf('.') > -1){
                var preText = Ext.util.Format.numberWord(strAmount.substr(0,strAmount.indexOf('.')));
                var postText = Ext.util.Format.numberWord(strAmount.substr(strAmount.indexOf('.')+1,strAmount.length));

                return Ext.String.format('#{{0}{2} {1}{3}}', preText, postText, currencyCodeKor, postCurrencyCodeKor);
            }else if(amount > 0){
                return Ext.String.format('#{{0}{1}}', Ext.util.Format.numberWord(amount), currencyCodeKor);
            }
        }
	 },
	 // 두 날짜 사이의 일수를 가져온다.
	 getCountPeriodDate : function (fromDate, toDate) {
		 if(fromDate && toDate) {
			 fromDate = Ext.Date.clearTime(fromDate);
			 toDate = Ext.Date.clearTime(toDate);
			 if(Ext.Date.isEqual(toDate, fromDate)){
				 return 1;
			 }
			 
			 var datePeriod = toDate - fromDate;
			 datePeriod = datePeriod /(1000 * 60 * 60 * 24);
			 return datePeriod > 0  ? datePeriod : null;
		 }
		 return null; 
	 }

});

//Custom Vtypes 
Ext.define('Site.override.form.field.VTypes',{
	override : 'Ext.form.field.VTypes',
	phoneMinLenthNine : /\d{9}$/, //9자리 정규식
	phoneMinLenthTen : /\d{10}$/, //10자리 정규식
	phone : function(value, field){
		if(Ext.String.startsWith(value , '02')) {
			return this.phoneMinLenthNine.test(value);
		}else{
			return this.phoneMinLenthTen.test(value);
		}
	},
	phoneText : '전화번호 자리수에 맞게 입력해야합니다.' //에러메시지
});

//엠로 로고 및 주소 보이지 않도록
Ext.define('Site.override.view.mdi.Viewport',{
	override : 'Mdi.view.mdi.Viewport',

	processMdiFoot : function(config){
		config.hidden = true;
		return config;
	}
});

//정합성
Ext.define('Site.util.Validation', {
	singleton : true,
	//사업자번호
	checkBusinessNo : function(value) {
		var strNumb = value;
		var sumMod = 0;
		sumMod += parseInt(strNumb.substring(0,1));
		sumMod += parseInt(strNumb.substring(1,2)) * 3 % 10;
		sumMod += parseInt(strNumb.substring(2,3)) * 7 % 10;
		sumMod += parseInt(strNumb.substring(3,4)) * 1 % 10;
		sumMod += parseInt(strNumb.substring(4,5)) * 3 % 10;
		sumMod += parseInt(strNumb.substring(5,6)) * 7 % 10;
		sumMod += parseInt(strNumb.substring(6,7)) * 1 % 10;
		sumMod += parseInt(strNumb.substring(7,8)) * 3 % 10;
		sumMod += Math.floor(parseInt(strNumb.substring(8,9)) * 5 / 10);
		sumMod += parseInt(strNumb.substring(8,9)) * 5 % 10;
		sumMod += parseInt(strNumb.substring(9,10));

		return !(sumMod % 10 != 0);
	},
	//주민등록번호
	checkCitizenNo : function(value){
		if(value.length != 13){
			return false;
		}
		var str1 = value.substring(0,6);
		var str2 = value.substring(6,13);
		var hap=0;
		for(var i=0; i<6; i++) {
			hap += ((str1.charAt(i))*(i+2));
		}
		hap += ((str2.charAt(0))*8);
		hap += ((str2.charAt(1))*9);
		for(var i=2; i<6; i++){
			hap += ((str2.charAt(i))*(i));
		}
		var namegi = hap%11;
		if((str2.charAt(0) == 5)||(str2.charAt(0) == 6)||(str2.charAt(0) == 7)||(str2.charAt(0) == 8)) {
			var res = 13 - namegi;
			if(res < 10) { 
				return ((str2.charAt(6))==(res));
			} else {
				return ((str2.charAt(6))==(res - 10));
			}
		} else {
			if(namegi == 0 ) {
			return ((str2.charAt(6))==1);
			}
			else if (namegi==1) {
				return ((str2.charAt(6))==0);
			}
			else {
				return ((str2.charAt(6))==(11 - namegi));
			}
		}
	},
	//패스워드
	checkPassChar : function(value){
		var alpUData = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
		var alpDData = "abcdefghijklmnopqrstuvwxyz";
		var numData = "1234567890";
		var splData = "~`!@#$%^&*()_-+=[]{}|;:'\"<>,.?/";

		var alpUChk = false;
		var alpDChk = false;
		var numChk = false;
		var splChk = false;
		
		var chkData = value;
		var result = {};
		

		for(var i=0; i<chkData.length; i++){
			if(alpUData.indexOf(chkData.charAt(i)) != -1){
				alpUChk = true;
			}
			if(alpDData.indexOf(chkData.charAt(i)) != -1){
				alpDChk = true;
			}
			if(numData.indexOf(chkData.charAt(i)) != -1){
				numChk = true;
			}
			if(splData.indexOf(chkData.charAt(i)) != -1){
				splChk = true;
			}

			if(  alpUData.indexOf(chkData.charAt(i)) == -1 && alpDData.indexOf(chkData.charAt(i)) == -1
			  &&  numData.indexOf(chkData.charAt(i)) == -1 &&  splData.indexOf(chkData.charAt(i)) == -1){
			  	result.successYn = false;
			  	result.msg = '#{영문대/소문자, 숫자, 특수문자만 사용가능합니다.}';
				return result;
			}
		} //for
		var tValues = new Array();
		if(alpUChk)
			tValues.push(true);
		if(alpDChk)
			tValues.push(true);
		if(numChk)
			tValues.push(true);
		if(splChk)
			tValues.push(true);
		
		switch(tValues.length){
			case 2 :
				if(chkData.length >= 10){
			  	result.successYn = true;
			  	return result;
				}else{
			  	result.successYn = false;
			  	result.msg = '#{2가지 조합인 경우, 10자리 이상 길이로 입력하세요.}';
			  	return result;
				}
			break;
			case 3 :
			case 4 :
				if(chkData.length >= 8){
			  	result.successYn = true;
			  	return result;
				}else{
			  	result.successYn = false;
			  	result.msg = '#{ 3가지 이상 조합인 경우, 8자리 이상 길이로 입력하세요.}';
			  	return result;
				}
			break;
		}
		result.successYn = false;
	  result.msg = '#{2가지 이상의 조합으로 입력하세요.}';
		return result;
	},
	//법인번호
	checkCorpNo : function(value){
		

		
		var sum = 0;
		var last = Ext.Number.from(value.charAt(12));
		var num = [1,2,1,2,1,2,1,2,1,2,1,2];
		for(var i = 0; i < 12; i ++) {
			sum += Ext.Number.from(value.charAt(i)) * num[i];
		}
		
		var returnValue = ((10 - sum%10) % 10 === last);
		// 현재 법인번호 유효성 검사에 통과하지 못하는 실업체의 유효한 법인번호를 예외로 통과시킴
		if(!returnValue) {
			if(value === '1950110002030') {
				returnValue = true;
			}
		}
		return returnValue; 
	},
	//법인번호 (한전용)
	validCorpNumber : function(value){
		if(value.length != 13) return false;

		//법인번호 체크는 안함 20160901
//		var reg1=/[0-9]{6}/i; 
//		var reg2=/[0-9]{7}/i;
//		if(reg1.test(value.substring(0,6)) && reg2.test(value.substring(6,13))) {
//			if(this.checkCitizenNo(value) || this.checkCorpNo(value)) {
//				return true; 
//			}
//		}
		return true; 
	}
});

//첨부파일 컬럼의 닫기 버튼 추가
Ext.define('Site.override.grid.column.Attachment',{
	override : 'Etna.grid.column.Attachment',

	closable : false,

	config : {
		windowWidth : 400,
		windowHeight : 300
	},

	defaultUploaderConfig : {
		hideUploadButton : false,
		hideCloseButton : false
	}
});

//TECHSUPP-610 포커스 전체 선택
//[2017.02.15 lms] mouseWheelEnabled : false 속성 추가 -> 넘버필드에 커서를 두고 마우스 휠 돌릴시, 값 증가 또는 감소 불가능하도록
Ext.define('Etna.override.form.field.Number', {
	override: 'Ext.form.field.Number',
	mouseWheelEnabled : false,
	
	initComponent : function(){
		var me = this;
		
		if(("numberfield"===me.xtype) && me.restrictInput){ // 키입력 제한 사용여부
			me.enforceMaxLength = true;
			me.maxLength = 17;
			me.enableKeyEvents = true; // keypress 이벤트를 위해
			me.maxPrecision = me.getMaxPrecisionFromCoverFormat();
			
			//마이너스(-) 입력이 가능한경우
			if(me.allowMinus){
				me.restrictRegex = me.minusRestrictRegex;
			}
			me.on('afterrender', me.restrictDecimalPrecisionListeners, me, {
				single: true
			});
		}
		
		me.callParent();
		me.callParent(arguments);
		me.selectOnFocus = me.editable;
	},
	setEditable : function(editable){
		var me = this;
		me.selectOnFocus = editable;
		me.callParent(arguments);
	},
	// 소수점 자릿수 6
	restrictRegex: {
		'0': /^\d{0,12}?$/,
		'1': /^\d{1,12}(\.\d{0,1})?$/,
		'2': /^\d{1,12}(\.\d{0,2})?$/,
		'3': /^\d{1,12}(\.\d{0,3})?$/,
		'4': /^\d{1,12}(\.\d{0,4})?$/,
		'5': /^\d{1,12}(\.\d{0,5})?$/,
		'6': /^\d{1,12}(\.\d{0,6})?$/
	},
	
	//마이너스 입력하능한 경우
	minusRestrictRegex: {
		'0': /^[-]?\d{0,12}?$/,
		'1': /^[-]?\d{1,12}(\.\d{0,1})?$/,
		'2': /^[-]?\d{1,12}(\.\d{0,2})?$/,
		'3': /^[-]?\d{1,12}(\.\d{0,3})?$/,
		'4': /^[-]?\d{1,12}(\.\d{0,4})?$/,
		'5': /^[-]?\d{1,12}(\.\d{0,5})?$/,
		'6': /^[-]?\d{1,12}(\.\d{0,6})?$/
	},
	
	restrictCoverFormat: {
		'0': '0,000',
		'1': '0,000.#',
		'2': '0,000.##',
		'3': '0,000.###',
		'4': '0,000.####',
		'5': '0,000.#####',
		'6': '0,000.######'
	},
	
	/** 키입력 제한을 위한 리스너 등록 */
	restrictDecimalPrecisionListeners: function(){
		var me = this;
		
		me.on('keypress', me.restrictDecimalPrecisionPressHandler, me);
		me.inputEl.on('paste', me.restrictInputPasteHandler, me);
	},
	
	/** [Event] KeyPress */
	restrictDecimalPrecisionPressHandler: function(field, event){
		var me = this,
			inputValue = String.fromCharCode(event.charCode),
			value = me.getRawValue();
	
		if(value == null){
			value = '';
		}
		
		me.decimalPrecisionInput(event, value.toString(), inputValue);
	}
});

Ext.define('Etna.override.Component', {
	 override : 'Ext.Component',
	 setActive : function(active, newActive, doFocus){
		 var me = this;
		 
		 if(active){
			 me.callParent(arguments);
		 }else{
			 if(me.isWindow && (newActive && newActive.isWindow) && me.hideShadowOnDeactivate){
				 me.el.disableShadow();
			 }
			 me.fireEvent('deactivate', me);
			 me.previousFocus = null;
		 }
	},
	/** Splitter 버그 */
	getWidth: function(){
		return this.el ? this.el.getWidth() : 0;
	},
	/** Splitter 버그 */
	getHeight: function(){
		return this.el ? this.el.getHeight() : 0;
	}
});

if(window.MakeINIpluginData){
	Ext.define('Initech.Mdi.override.data.Connection', {
		override : 'Ext.data.Connection',

		setOptions : function(options, scope) {
			var me = this;
			var result = me.callParent(arguments);
			if(options.initechParams){
				result.data = "INIpluginData=" + URLEncode(MakeINIpluginData(null, Ext.Object.toQueryString(options.params)));
				options.disabledInitechHeader = true;
			}
			return result;
		}
	});
}

Ext.define('Initech.Mdi.view.mdi.authenticator.StandardViewController',{
	override : 'Mdi.view.mdi.authenticator.StandardViewController',
	login: function() {
		var me = this,
		vm = me.getViewModel(),
		view = me.getView();
		if (!view.isValid()) {
			Ext.Msg.alert('#{주의}', '#{로그인 데이터가 유효하지 않습니다.}');
			return;
		}
		var authentication = vm.get('authentication');
		return new Promise(function(resolve, reject) {
			Ext.Ajax.request({
				url: 'loginProcess.do',
				method: 'POST',
				params: authentication,
				initechParams : true,
				success: function(response) {
					if (response.responseText) {
						reject(response.responseText);
					} else {
						resolve();
					}
				},
				failure: function() {
					reject('오류 발생');
				}
			});
		});
	}
});

//Initech 전체 데이터 암호화 처리 설정
Ext.define('Initech.override.data.proxy.Server', {
	override : 'Ext.data.proxy.Server',
	initech  : false
});

//CheckboxModel checkOnly:true 속성 추가
Ext.define('Site.override.selection.CheckboxModel', {
	override : 'Ext.selection.CheckboxModel',

	checkOnly: true
});

//paging toolbar 사용자 입력 영역 길이 조정
Ext.define('Site.override.toolbar.Paging', {
	override : 'Ext.toolbar.Paging',
	inputItemWidth : 50
});

Ext.define('Mdi.override.view.mdi.authenticator.StandardViewController',{
	override : 'Mdi.view.mdi.authenticator.StandardViewController',
	initComponent : function() {

	},
	onTextfieldSpecialkey : function(field, e, eOpts) {
		var me = this;
		if (e.getKey() == e.ENTER) {
			me.login().then(function() {
				location.reload();
			}, function(message) {
				Ext.Msg.alert('#{주의}', message);
			});
		}
	}
});
Ext.define('Mdi.override.view.mdi.UserInfo', {
	override : 'Mdi.view.mdi.UserInfo',
	modal:true,
	draggable : true,
	initComponent : function() {
		var me = this;
		this.closable = false;
		me.userInfoListeners = me.on('show', me.refresh, me, {destroyable : true});
		me.callParent(arguments);
	},

	processUserInfoForm : function(config) {
		Ext.Array.each(config.items, function(item) {
			if(item.reference == ('phoneNo') ){
				item.vtype = 'phone';
				item.plugins=[{ptype : 'inputcover'}];
			}
			if(item.reference == ('mobileNo') ){
				item.vtype = 'phone';
				item.plugins=[{ptype : 'inputcover'}];
			}
			if(item.reference == ('faxNo') ){
				item.vtype = 'phone';
				item.plugins=[{ptype : 'inputcover'}];
			}
			item.listeners = {
					change : function(field, newValue, oldValue) {
						if(item.reference == ('phoneNo') ){
							var number = Site.util.Format.phone(field, '({0}){1}-{2}');
							field.setCover(number);
						}
						if(item.reference == ('mobileNo') ){
							var number = Site.util.Format.phone(field, '({0}){1}-{2}');
							field.setCover(number);
						}
						if(item.reference == ('faxNo') ){
							var number = Site.util.Format.phone(field, '({0}){1}-{2}');
							field.setCover(number);
						}
						if(item.reference == ('companyName')){
							if(Cmmn.User.get('userType') == 'External'){
								field.setValue(Cmmn.User.get('vendorName'));
							}
						}
					}	
			};
		});
		return config;
	},

	refresh : function() {
		var me = this.getController();
		vm = me.getViewModel(),
		view = me.getView();
		view.setLoading(true);
		Etna.onDone(function() {
			var userData = me.getUserData();
			vm.set('userData', userData);
			view.setLoading(false);
		});
	},

	destroy : function() {
		var me = this;
		Ext.destroy(me.userInfoListeners);
		me.callParent(arguments);

	}

});

Ext.define('Etna.override.grid.plugin.Block', {
	override : 'Etna.grid.plugin.Block',
	
	getContextItems : function(){
		var me = this;
		return [{
			text : me.menuLabels.copy,
			iconCls : 'copy',
			handler : me.onCopyCommand,
			scope : me
		},{
			text : me.menuLabels.paste,
			iconCls : 'paste',
			handler : me.onPasteCommand,
			scope : me
		}];
	}
});

Ext.define('Etna.override.toolbar.Paging', {
	override : 'Ext.toolbar.Paging',
	
	defaultButtonUI : 'paging-toolbar'
	
});

//TECHSUPP-821 그리드에서 콤보벅스 컬럼 이미지 표현하기
Ext.define('Site.override.grid.column.Store', {
	override : 'Etna.grid.column.Store',
	
	comboColCls : Ext.baseCSSPrefix + 'grid-combo-column',
	
	defaultRenderer: function(value, meta){
		var me = this,
			editor;
		if(Ext.isFunction(me.getEditor) && (editor = me.getEditor())) {
			if(editor.xtype === 'combobox'){
				if(!meta.tdCls){
					meta.tdCls = '';
				}
				meta.tdCls += ' ';
				meta.tdCls += me.comboColCls;
			}
		}
		return me.callParent(arguments);
	}
});

//TECHSUPP-879 그리드 편집시 one click으로 편집 가능
Ext.define('Site.override.grid.plugin.CellEditing',{
	override : 'Ext.grid.plugin.CellEditing',
	clicksToEdit : 1
});

//paging 수 100으로 수정
Ext.define('Site.override.data.Store', {
	override : 'Ext.data.Store'
}, function(clazz) {
	clazz.getConfigurator().reconfigure(clazz.prototype, {pageSize : 100});
});

Ext.define('Etna.override.form.field.Text', {
	override : 'Ext.form.field.Text',
	
	// 정수 15자리, 소수 6자리
	restrictRegex: {
		'0': /^\d{0,15}?$/,
		'1': /^\d{1,15}(\.\d{0,1})?$/,
		'2': /^\d{1,15}(\.\d{0,2})?$/,
		'3': /^\d{1,15}(\.\d{0,3})?$/,
		'4': /^\d{1,15}(\.\d{0,4})?$/,
		'5': /^\d{1,15}(\.\d{0,5})?$/,
		'6': /^\d{1,15}(\.\d{0,6})?$/,
	},
	
	restrictCoverFormat: {
		'0': '0,000',
		'1': '0,000.#',
		'2': '0,000.##',
		'3': '0,000.###',
		'4': '0,000.####',
		'5': '0,000.#####',
		'6': '0,000.######'
	},
	
	/** BigNumber를 통해, trim로직을 수행할 이벤트 등록 */
	trimBigNumberEvents: [
		'focus', 'blur'
	],
	
	initComponent: function(){
		var me = this;
		
		if(("textfield" === me.xtype) && me.restrictInput){
			me.enableKeyEvents = true;
			me.maskRe = /[0-9.]/;
			if(me.coverFormat){
				me.maxPrecision = me.getMaxPrecisionFromCoverFormat();
			}
			me.on('afterrender', me.restrictInputListeners, me, {
				single: true
			});
		}
		
		me.callParent();
	},
	
	/** TestField 입력제한 */
	restrictInputListeners: function(){
		var me = this;
		
		Ext.Array.each(me.trimBigNumberEvents, function(event){
			me.on(event, me.restrictInputFocusHandler, me);
		})
		me.on('keydown', me.restrictInputKeydownHandler, me);
		me.on('keypress', me.restrictInputKeypressHandler, me);
		me.inputEl.on('paste', me.restrictInputPasteHandler, me);
	},
	
	/** [Event] trimBigNumberEvents */
	restrictInputFocusHandler: function(field, event){
		var me = this,
			value = me.getValue();
		
		if(!Ext.isEmpty(value)){
			me.setValue(new BigNumber(me.trimValue(value)).toString());
		}
	},
	
	/** [Event] KeyDown */
	restrictInputKeydownHandler: function(field, event){
		var me = this,
			charCode = event.getCharCode(),
			candidate = field.getRawValue(),
			selectionStart = event.currentTarget.selectionStart,
			selectionEnd = event.currentTarget.selectionEnd,
			stringCharCode = String.fromCharCode(charCode);
		
		if(charCode === event.BACKSPACE || charCode === event.DELETE){
			if( (Ext.isDefined(selectionStart)) ){
				if(selectionStart !== selectionEnd){
					candidate = me.deletePartOfString(candidate, selectionStart, selectionEnd);
				}else{
					if(charCode === event.BACKSPACE){
						selectionStart = selectionStart - 1;
					}else{
						selectionEnd = selectionEnd + 1;
					}
					
					candidate = me.deletePartOfString(candidate, selectionStart, selectionEnd);
				}
			}
			
			if(!me.isChangedValueOk(candidate)){
				event.stopEvent();
			}
		}else{
			/** IE, Chrome */
			if(charCode === 229){
				event.stopEvent();
			}
			field.setValue(me.trimValue(field.getValue()));
		}
	},
	
	/** 한글입력 시, Trim */
	trimValue: function(value){
		if(Ext.isEmpty(value)){
			return value;
		}else{
			return value.replace(/[ㄱ-ㅎㅏ-ㅣ가-힣 ]/g, '');
		}
	},
	
	/** [Event] KeyPress */
	restrictInputKeypressHandler: function(field, event){
		var me = this,
			inputValue = String.fromCharCode(event.charCode);
			value = me.getRawValue();
		
		me.decimalPrecisionInput(event, value, inputValue);
	},
	
	/** [Event] Paste */
	restrictInputPasteHandler: function(event, field){
		var me = this,
			value = me.getRawValue(),
			inputValue = '',
			clipboard = (event && event.browserEvent && event.browserEvent.clipboardData) ? event.browserEvent.clipboardData : false;
		
		if (clipboard && clipboard.getData) {
            if (/text\/plain/.test(clipboard.types)) {
            	inputValue = clipboard.getData('text/plain');
            } else if (/text\/html/.test(clipboard.types)) {
            	inputValue = clipboard.getData('text/html');
            }
         
            if(!Ext.isEmpty(inputValue)){
            	me.decimalPrecisionInput(event, value.toString(), inputValue);
            }
        }
	},
	
	/** KeyPress, Paste에 대한 키제한 로직 */
    decimalPrecisionInput: function(event, value, inputValue){
    	var me = this, candidate = value,
    		selectionStart = event.currentTarget.selectionStart,
    		selectionEnd = event.currentTarget.selectionEnd;
    	
		// IE8에서는 selectionStart가 undefined
		if(Ext.isDefined(selectionStart)){
			
			// 1. 블럭지정 삭제
			if(selectionStart !== selectionEnd){
				candidate = me.deletePartOfString(candidate, selectionStart, selectionEnd);
			}
			
			// 2. 입력된 키값 Insert
			candidate = Ext.String.insert(candidate, inputValue, selectionStart);
			
			if(!me.isChangedValueOk(candidate)){
				event.stopEvent();
			}
		}
    },
    
    /** 정규식을 통해, 변경된 값의 유효성 체크 */
    isChangedValueOk: function(candidate){
    	var me = this;
    	
    	for(var i=0; i<Object.keys(me.restrictRegex).length; i++){
			if((i<=me.maxPrecision) && me.restrictRegex[i].test(candidate)){
				me.currentDecimalPrecision = i;
				if(me.coverFormat){
					me.coverFormat = me.restrictCoverFormat[i];
				}
				return true;
			}
		}
    	return false;
    },
    
    /** String의 start-end영역만큼 삭제 */
    deletePartOfString: function(v, start, end){
    	var me = this,
    		vArr = v.split('');
    	
    	for(var i=start; i<end; i++){
    		vArr[i] = '';
    	}
    	
    	return vArr.join('');
    },
    
    // 추가
	getMaxPrecisionFromCoverFormat: function(){
		var me = this, 
			coverFormat = me.coverFormat;
		
		if(coverFormat){
			var decimalPointIndex = coverFormat.indexOf('.'),
				endIndex = coverFormat.length - 1;
			
			if(decimalPointIndex == -1){
				return 0;
			}
			
			return endIndex - decimalPointIndex;
		}
	}
});
//TECHSUPP-971 numberfield 소수점 입력 제한 
//Ext.define('Etna.override.form.field.Number', {
//	override : 'Ext.form.field.Number',
//	// 소수점에 따른 키입력 제한 기능
//	decimalPrecisionInput: function(field, e){
//		var me = this, v = field.getRawValue(), 
//			regExp = new RegExp('\\.\\d{'+me.decimalPrecision+',}'), // 정규식
//			pointIndex = v.indexOf(me.decimalSeparator), // 소수점 위치
//			selectionStart = e.parentEvent.currentTarget.selectionStart, // 커서 (드래그 시작)위치
//			selectionEnd = e.parentEvent.currentTarget.selectionEnd; // 커서 (드래그 끝)위치
//                                    		
//		// Decimal Point(소수점) 있으면,
//		if(!Ext.isEmpty(v) && (pointIndex>=0)){
//			if(Ext.isEmpty(selectionStart)){
//				// IE8에서는 selectionStart,End값이 없음
//				if (regExp.test(v)) {
//					e.stopEvent();
//				}
//			}else{
//				// 값을 입력한 위치가 Decimal Point Index보다 크면, (소수점 아래에서 키가 입력되었다면)
//				if(pointIndex < selectionStart && pointIndex < selectionEnd){
//					if (regExp.test(v)) {
//						e.stopEvent();
//					}
//				}
//			}// end else
//		}
//	}
//});

//TECHSUPP-1088 소수점 제어(kind)
Ext.define('Site.override.util.NumberKind', {
	override : 'Etna.util.NumberKind'
}, function(clazz){
	clazz.addSetting('symbolN', Ext.create('Etna.util.NumberKindSetting', {
		decimalPrecision: 0,
		format: '0,000'
	}));
	clazz.addSetting('symbolP', Ext.create('Etna.util.NumberKindSetting', {
		decimalPrecision: 3,
		format: '0,000.###'
	}));
	clazz.addSetting('symbolNormal', Ext.create('Etna.util.NumberKindSetting', {
		decimalPrecision: 6,
		format: '0,000.######'
	}));
});



/**
 로그인 비밀번호 3개월마다 변경하는 팝업 기능개선 (행안부 기준) 
 */
Ext.env.Ready.on(function() {
	Ext.define('Mdi.override.view.mdi.popup.ChangePasswordPopupViewController', {
	    override: 'Mdi.view.mdi.popup.ChangePasswordPopupViewController',
	    onChangeButtonClick: function(button, e, eOpts) { // 저장 버튼 클릭
	        var me = this;
	        pageMove('myInfo');
	        me.getView().close();
	    }
	});
});

Ext.define('Etna.override.upload.ui.Grid', {
	override : 'Etna.upload.ui.Grid',
	
	selModel: {
        checkOnly: true,
        mode: 'SIMPLE',
        headerWidth : 54,
        getHeaderConfig: function() {
            var me = this,
                showCheck = me.showHeaderCheckbox !== false;     

            return {
                isCheckerHd: showCheck,
                text : '&#160;',
                align : 'center',
                clickTargetName: 'el',
                width: me.headerWidth,
                sortable: false,
                draggable: false,
                resizable: false,
                hideable: false,
                menuDisabled: true,
                dataIndex: '',
                tdCls: me.tdCls,
                cls: showCheck ? Ext.baseCSSPrefix + 'column-header-checkbox ' : '',
                defaultRenderer: me.renderer.bind(me),
                editRenderer: me.editRenderer || me.renderEmpty,
                locked: me.hasLockedHeader(),
                listeners : {
                	afterrender : function(cmp) {
                		cmp.titleEl.insertHtml('afterBegin', Ext.String.format('<div style="position:absolute;left:22px;">{0}</div>', '#{삭제}'));
                	}
                }
            };
        },
        renderer: function(value, metaData, record, rowIndex, colIndex, store, view) {
            return '<div class="' + Ext.baseCSSPrefix + 'grid-row-checker" style="margin:auto;" role="presentation">&#160;</div>';
        }
    }
});

Ext.define('Etna.override.exporter.RemotingProvider', {
	override : 'Etna.exporter.RemotingProvider',
	compressWorkerUri : 'resources/worker/exporter-compress.js'
});
Ext.define('Etna.override.exporter.CSVProvider', {
	override : 'Etna.exporter.CSVProvider',
	dataWorkerUri : 'resources/worker/exporter-data.js'
}, function() {
	Etna.exporter.Manager.addProvider(new Etna.exporter.CSVProvider());
	Etna.exporter.Manager.addProvider(new Etna.exporter.XLSXProvider());
});


//TECHSUPP-1487 첨부컬럼 컴포넌트 확장 (입찰참가신청 필수 첨부, 기타첨부 한번에 호출하도록)
Ext.define('Site.override.grid.column.Attachment', {
	extend : 'Etna.grid.column.Attachment',
	alias : 'widget.bidattendattachmentcolumn',
	
	config : {
		/**
		 * @cfg {Etna.upload.Uploader} uploader 
		 * @accessor
		 * 첨부파일 컴포넌트
		 */
		uploader : null,
		/**
		 * @cfg {Etna.upload.Uploader} uploader config 
		 * @accessor
		 * 첨부파일 컴포넌트 config
		 */
		uploaderConfig : {},
		
		windowWidth : 500,
		
		windowHeight : 350
	},
	
	cls : Ext.baseCSSPrefix + 'etna-attachment-column',
	
	/**
	 * @cfg {String} align
	 */
	align : 'right',
	
	/**
	 * @cfg {String} closeConfirmTitle
	 * Confirm MessageBox 타이틀
	 */
	closeConfirmTitle : '첨부파일 알림',
	/**
	 * @cfg {String} closeConfirmMessage
	 * Confirm MessageBox 메세지
	 */
	closeConfirmMessage : '저장(삭제)되지 않은 첨부파일이 있습니다.<br>저장하시겠습니까?',
	
	/**
	 * @cfg {String} countDataIndex
	 * 첨부파일 카운트 dataIndex
	 */
	countDataIndex : 'fileGroupCount',
	
	/**
	 * @cfg {Boolean} readOnly
	 * 첨부파일 버튼 활성화 여부
	 */
	readOnly : false,
	
	/**
	 * @cfg {Function} isDisabled
	 * 액션컬럼의 item 의 비활성화 여부 리턴 함수 
	 */
	isDisabled : null,
	
	/**
	 * @cfg {Boolean} closable
	 * close tool 사용여부 
	 */
	closable : false,
	
	defaultUploaderConfig : {
		hideUploadButton : false,
		hideCloseButton : false
	},
	
	/**
	 * @constructor
	 * @param {Object} config 설정
	 */
	constructor : function(config) {
		var me = this;
		Ext.applyIf(config, {
			renderer : function(value, metadata, record, rowIndex, colIndex, store, view) {
				var count = record.get(me.countDataIndex) || 0;
				return '<span class="grid-attachment-text">' + count +'</span>';
				//return '<span class="grid-attachment-text">첨부파일</span>';
			},
			items : [{
				iconCls : 'grid-attachment-icon',
				tooltip : '첨부파일',
				handler : me.onHandler,
				isDisabled : me.isDisabled
			}]
		});
		me.callParent(arguments);
	},
	
	/**
	 * @private onHandler
	 * @param {Ext.panel.Grid} grid GridPanel
	 * @param {Number} rowIndex
	 * @param {Number} colIndex,
	 * Action 컬럼의 클릭 핸들러 첨부파일 컴포넌트를 {Ext.window.Window} 를 이용하여 팝업으로 띄움
	 */
	onHandler : function(grid, rowIndex, colIndex) {
		var me = this,
			view = me.getView(),
			record = grid.getStore().getAt(rowIndex),
			win = me.createAttachment(record),
			attachmentfield = win.down('bidattendattachmentfield');
			
		if(me.fireEvent('beforeattachmentshow', attachmentfield, record, rowIndex, colIndex, view) === false) {
			win.close();
			return;
		}
		win.show();
		me.fireEvent('attachmentshow', attachmentfield, record, rowIndex, colIndex, view);
		return win;
	},
	
	/**
	 * @private
	 */
	createAttachment : function(record) {
		var me = this,
			config = Ext.apply(Ext.clone(me.defaultUploaderConfig), me.getUploaderConfig()),
			fileGroupValue = record.get(me.dataIndex),
			win;
			
		return (win = Ext.create('Ext.window.Window', {
			title : '첨부파일',
			layout : 'fit',
			width : me.getWindowWidth(),
			height : me.getWindowHeight(),
			modal : true,
			closable : me.closable,
			readOnly : me.readOnly,
			items : Ext.apply(config, {
				xtype : 'bidattendattachmentfield',
				name : me.dataIndex,
				readOnly : me.readOnly,
				listeners : {
					uploadstart : function() {
						var closeButton;
						if(me.closable) {
							closeButton = win.tools[0];
							closeButton.disable();	
						}
					},
					loadcompleted : function() {
						var closeButton;
						if(me.closable) {
							closeButton = win.tools[0];
							closeButton.enable();
						}
						record.set(me.countDataIndex, this.getStore().getCount());
						if(win.closeWindowAfterUploadCompleted) {
							win.doClose();
						}
					},
					bindingvaluechange : function(value) {
						record.set(me.dataIndex, value);
					},
					uploaderclose : function() {
						win.doClose();
					}
				}
			}),
			listeners : {
				afterrender : function(self) {
					var uploader = self.down('bidattendattachmentfield');
					uploader.setValue(fileGroupValue);
					me.setUploader(uploader.getUploader());
				},
				beforeclose : function(self) {
					var uploader = self.down('bidattendattachmentfield');
					if(uploader.hasUploadFiles()) {
						Ext.Msg.show({
							title : me.closeConfirmTitle,
							msg : me.closeConfirmMessage,
							buttons : Ext.Msg.YESNOCANCEL,
							icon : Ext.MessageBox.QUESTION,
							fn : function(btn, text) {
								if(btn == "yes") {
									win.closeWindowAfterUploadCompleted = true;
									uploader.upload();
								}
								else if(btn == "no") {
									win.doClose();
								}
							}
						});
						return false;
					}
				},
				close : function() {
					me.setUploader(null);
				},
				scope : me
			}
		}));
	},
	
	/**
	 * @method setReadOnly
	 * @param {Boolean} value 읽기속성
	 */
	setReadOnly : function(value) {
		var me = this,
			uploader = me.getUploader();
		
		if(uploader) {
			uploader.setReadOnly(value);
		}
		Ext.apply(me.getUploaderConfig(), {
			readOnly : value
		});
		me.readOnly = value;
	},
	
	/**
	 * @method getReadOnly
	 */
	getReadOnly : function() {
		var me = this;
		return me.readOnly;
	}
});

Ext.define('Site.extends.upload.StoreBasedUploader', {
	extend : 'Etna.upload.StoreBasedUploader',
	listUrl : 'smartsuit.ui.etnajs.cmmn.CommonController.getBidAttendRequestAllAttachments'
});

Ext.define('Site.override.form.field.Attachment', {
	extend : 'Etna.form.field.Attachment',
	alias : 'widget.bidattendattachmentfield',
	
	uploaderClass : 'Site.extends.upload.StoreBasedUploader'
});

//첨부컬럼 컴포넌트 확장 (여러 규격검토자의 첨부파일을 한번에 호출하도록)
Ext.define('Site.override.grid.column.SpecEvalAttachment', {
	extend : 'Etna.grid.column.Attachment',
	alias : 'widget.specevalattachmentcolumn',
	
	config : {
		/**
		 * @cfg {Etna.upload.Uploader} uploader 
		 * @accessor
		 * 첨부파일 컴포넌트
		 */
		uploader : null,
		/**
		 * @cfg {Etna.upload.Uploader} uploader config 
		 * @accessor
		 * 첨부파일 컴포넌트 config
		 */
		uploaderConfig : {},
		
		windowWidth : 500,
		
		windowHeight : 350
	},
	
	cls : Ext.baseCSSPrefix + 'etna-attachment-column',
	
	/**
	 * @cfg {String} align
	 */
	align : 'right',
	
	/**
	 * @cfg {String} closeConfirmTitle
	 * Confirm MessageBox 타이틀
	 */
	closeConfirmTitle : '첨부파일 알림',
	/**
	 * @cfg {String} closeConfirmMessage
	 * Confirm MessageBox 메세지
	 */
	closeConfirmMessage : '저장(삭제)되지 않은 첨부파일이 있습니다.<br>저장하시겠습니까?',
	
	/**
	 * @cfg {String} countDataIndex
	 * 첨부파일 카운트 dataIndex
	 */
	countDataIndex : 'fileGroupCount',
	
	/**
	 * @cfg {Boolean} readOnly
	 * 첨부파일 버튼 활성화 여부
	 */
	readOnly : false,
	
	/**
	 * @cfg {Function} isDisabled
	 * 액션컬럼의 item 의 비활성화 여부 리턴 함수 
	 */
	isDisabled : null,
	
	/**
	 * @cfg {Boolean} closable
	 * close tool 사용여부 
	 */
	closable : false,
	
	defaultUploaderConfig : {
		hideUploadButton : false,
		hideCloseButton : false
	},
	
	/**
	 * @constructor
	 * @param {Object} config 설정
	 */
	constructor : function(config) {
		var me = this;
		Ext.applyIf(config, {
			renderer : function(value, metadata, record, rowIndex, colIndex, store, view) {
				var count = record.get(me.countDataIndex) || 0;
				return '<span class="grid-attachment-text">' + count +'</span>';
				//return '<span class="grid-attachment-text">첨부파일</span>';
			},
			items : [{
				iconCls : 'grid-attachment-icon',
				tooltip : '첨부파일',
				handler : me.onHandler,
				isDisabled : me.isDisabled
			}]
		});
		me.callParent(arguments);
	},
	
	/**
	 * @private onHandler
	 * @param {Ext.panel.Grid} grid GridPanel
	 * @param {Number} rowIndex
	 * @param {Number} colIndex,
	 * Action 컬럼의 클릭 핸들러 첨부파일 컴포넌트를 {Ext.window.Window} 를 이용하여 팝업으로 띄움
	 */
	onHandler : function(grid, rowIndex, colIndex) {
		var me = this,
			view = me.getView(),
			record = grid.getStore().getAt(rowIndex),
			win = me.createAttachment(record),
			attachmentfield = win.down('specevalattachmentfield');
			
		if(me.fireEvent('beforeattachmentshow', attachmentfield, record, rowIndex, colIndex, view) === false) {
			win.close();
			return;
		}
		win.show();
		me.fireEvent('attachmentshow', attachmentfield, record, rowIndex, colIndex, view);
		return win;
	},
	
	/**
	 * @private
	 */
	createAttachment : function(record) {
		var me = this,
			config = Ext.apply(Ext.clone(me.defaultUploaderConfig), me.getUploaderConfig()),
			fileGroupValue = {
				bidId : record.get(me.dataIndex),
				vendorId : record.get('vendorId')
			},
			win;
			
		return (win = Ext.create('Ext.window.Window', {
			title : '첨부파일',
			layout : 'fit',
			width : me.getWindowWidth(),
			height : me.getWindowHeight(),
			modal : true,
			closable : me.closable,
			readOnly : me.readOnly,
			items : Ext.apply(config, {
				xtype : 'specevalattachmentfield',
				name : me.dataIndex,
				readOnly : me.readOnly,
				listeners : {
					uploadstart : function() {
						var closeButton;
						if(me.closable) {
							closeButton = win.tools[0];
							closeButton.disable();	
						}
					},
					loadcompleted : function() {
						var closeButton;
						if(me.closable) {
							closeButton = win.tools[0];
							closeButton.enable();
						}
						record.set(me.countDataIndex, this.getStore().getCount());
						if(win.closeWindowAfterUploadCompleted) {
							win.doClose();
						}
					},
					bindingvaluechange : function(value) {
						record.set(me.dataIndex, value);
					},
					uploaderclose : function() {
						win.doClose();
					}
				}
			}),
			listeners : {
				afterrender : function(self) {
					var uploader = self.down('specevalattachmentfield');
					uploader.setValue(fileGroupValue);
					me.setUploader(uploader.getUploader());
				},
				beforeclose : function(self) {
					var uploader = self.down('specevalattachmentfield');
					if(uploader.hasUploadFiles()) {
						Ext.Msg.show({
							title : me.closeConfirmTitle,
							msg : me.closeConfirmMessage,
							buttons : Ext.Msg.YESNOCANCEL,
							icon : Ext.MessageBox.QUESTION,
							fn : function(btn, text) {
								if(btn == "yes") {
									win.closeWindowAfterUploadCompleted = true;
									uploader.upload();
								}
								else if(btn == "no") {
									win.doClose();
								}
							}
						});
						return false;
					}
				},
				close : function() {
					me.setUploader(null);
				},
				scope : me
			}
		}));
	},
	
	/**
	 * @method setReadOnly
	 * @param {Boolean} value 읽기속성
	 */
	setReadOnly : function(value) {
		var me = this,
			uploader = me.getUploader();
		
		if(uploader) {
			uploader.setReadOnly(value);
		}
		Ext.apply(me.getUploaderConfig(), {
			readOnly : value
		});
		me.readOnly = value;
	},
	
	/**
	 * @method getReadOnly
	 */
	getReadOnly : function() {
		var me = this;
		return me.readOnly;
	}
});

Ext.define('Site.extends.upload.SpecEvalStoreBasedUploader', {
	extend : 'Etna.upload.StoreBasedUploader',
	listUrl : 'smartsuit.ui.etnajs.cmmn.CommonController.getSpecEvalResultAllAttachments'
});

Ext.define('Site.override.form.field.SpecEvalAttachment', {
	extend : 'Etna.form.field.Attachment',
	alias : 'widget.specevalattachmentfield',
	
	uploaderClass : 'Site.extends.upload.SpecEvalStoreBasedUploader',
});

//첨부컬럼 컴포넌트 확장 (여러 규격검토자의 GIS첨부파일을 한번에 호출하도록)
Ext.define('Site.override.grid.column.GisAttachment', {
	extend : 'Etna.grid.column.Attachment',
	alias : 'widget.gisattachmentcolumn',
	
	config : {
		/**
		 * @cfg {Etna.upload.Uploader} uploader 
		 * @accessor
		 * 첨부파일 컴포넌트
		 */
		uploader : null,
		/**
		 * @cfg {Etna.upload.Uploader} uploader config 
		 * @accessor
		 * 첨부파일 컴포넌트 config
		 */
		uploaderConfig : {},
		
		windowWidth : 500,
		
		windowHeight : 350
	},
	
	cls : Ext.baseCSSPrefix + 'etna-attachment-column',
	
	/**
	 * @cfg {String} align
	 */
	align : 'right',
	
	/**
	 * @cfg {String} closeConfirmTitle
	 * Confirm MessageBox 타이틀
	 */
	closeConfirmTitle : '첨부파일 알림',
	/**
	 * @cfg {String} closeConfirmMessage
	 * Confirm MessageBox 메세지
	 */
	closeConfirmMessage : '저장(삭제)되지 않은 첨부파일이 있습니다.<br>저장하시겠습니까?',
	
	/**
	 * @cfg {String} countDataIndex
	 * 첨부파일 카운트 dataIndex
	 */
	countDataIndex : 'fileGroupCount',
	
	/**
	 * @cfg {Boolean} readOnly
	 * 첨부파일 버튼 활성화 여부
	 */
	readOnly : false,
	
	/**
	 * @cfg {Function} isDisabled
	 * 액션컬럼의 item 의 비활성화 여부 리턴 함수 
	 */
	isDisabled : null,
	
	/**
	 * @cfg {Boolean} closable
	 * close tool 사용여부 
	 */
	closable : false,
	
	defaultUploaderConfig : {
		hideUploadButton : false,
		hideCloseButton : false
	},
	
	/**
	 * @constructor
	 * @param {Object} config 설정
	 */
	constructor : function(config) {
		var me = this;
		Ext.applyIf(config, {
			renderer : function(value, metadata, record, rowIndex, colIndex, store, view) {
				var count = record.get(me.countDataIndex) || 0;
				return '<span class="grid-attachment-text">' + count +'</span>';
				//return '<span class="grid-attachment-text">첨부파일</span>';
			},
			items : [{
				iconCls : 'grid-attachment-icon',
				tooltip : '첨부파일',
				handler : me.onHandler,
				isDisabled : me.isDisabled
			}]
		});
		me.callParent(arguments);
	},
	
	/**
	 * @private onHandler
	 * @param {Ext.panel.Grid} grid GridPanel
	 * @param {Number} rowIndex
	 * @param {Number} colIndex,
	 * Action 컬럼의 클릭 핸들러 첨부파일 컴포넌트를 {Ext.window.Window} 를 이용하여 팝업으로 띄움
	 */
	onHandler : function(grid, rowIndex, colIndex) {
		var me = this,
			view = me.getView(),
			record = grid.getStore().getAt(rowIndex),
			win = me.createAttachment(record),
			attachmentfield = win.down('gisAttachmentfield');
			
		if(me.fireEvent('beforeattachmentshow', attachmentfield, record, rowIndex, colIndex, view) === false) {
			win.close();
			return;
		}
		win.show();
		me.fireEvent('attachmentshow', attachmentfield, record, rowIndex, colIndex, view);
		return win;
	},
	
	/**
	 * @private
	 */
	createAttachment : function(record) {
		var me = this,
			config = Ext.apply(Ext.clone(me.defaultUploaderConfig), me.getUploaderConfig()),
			fileGroupValue = {
				bidId : record.get(me.dataIndex),
				vendorId : record.get('vendorId')
			},
			win;
			
		return (win = Ext.create('Ext.window.Window', {
			title : '첨부파일',
			layout : 'fit',
			width : me.getWindowWidth(),
			height : me.getWindowHeight(),
			modal : true,
			closable : me.closable,
			readOnly : me.readOnly,
			items : Ext.apply(config, {
				xtype : 'gisAttachmentfield',
				name : me.dataIndex,
				readOnly : me.readOnly,
				listeners : {
					uploadstart : function() {
						var closeButton;
						if(me.closable) {
							closeButton = win.tools[0];
							closeButton.disable();	
						}
					},
					loadcompleted : function() {
						var closeButton;
						if(me.closable) {
							closeButton = win.tools[0];
							closeButton.enable();
						}
						record.set(me.countDataIndex, this.getStore().getCount());
						if(win.closeWindowAfterUploadCompleted) {
							win.doClose();
						}
					},
					bindingvaluechange : function(value) {
						record.set(me.dataIndex, value);
					},
					uploaderclose : function() {
						win.doClose();
					}
				}
			}),
			listeners : {
				afterrender : function(self) {
					var uploader = self.down('gisAttachmentfield');
					uploader.setValue(fileGroupValue);
					me.setUploader(uploader.getUploader());
				},
				beforeclose : function(self) {
					var uploader = self.down('gisAttachmentfield');
					if(uploader.hasUploadFiles()) {
						Ext.Msg.show({
							title : me.closeConfirmTitle,
							msg : me.closeConfirmMessage,
							buttons : Ext.Msg.YESNOCANCEL,
							icon : Ext.MessageBox.QUESTION,
							fn : function(btn, text) {
								if(btn == "yes") {
									win.closeWindowAfterUploadCompleted = true;
									uploader.upload();
								}
								else if(btn == "no") {
									win.doClose();
								}
							}
						});
						return false;
					}
				},
				close : function() {
					me.setUploader(null);
				},
				scope : me
			}
		}));
	},
	
	/**
	 * @method setReadOnly
	 * @param {Boolean} value 읽기속성
	 */
	setReadOnly : function(value) {
		var me = this,
			uploader = me.getUploader();
		
		if(uploader) {
			uploader.setReadOnly(value);
		}
		Ext.apply(me.getUploaderConfig(), {
			readOnly : value
		});
		me.readOnly = value;
	},
	
	/**
	 * @method getReadOnly
	 */
	getReadOnly : function() {
		var me = this;
		return me.readOnly;
	}
});

Ext.define('Site.extends.upload.GisStoreBasedUploader', {
	extend : 'Etna.upload.StoreBasedUploader',
	listUrl : 'smartsuit.ui.etnajs.cmmn.CommonController.getGisAllAttachments'
});

Ext.define('Site.override.form.field.GisAttachment', {
	extend : 'Etna.form.field.Attachment',
	alias : 'widget.gisAttachmentfield',
	
	uploaderClass : 'Site.extends.upload.GisStoreBasedUploader'
});

// Component Refresh 버튼이 기본적으로 들어감 기본 Refresh 버튼 삭제
Ext.define('Site.override.Portal.controller.ComponentFactory', {
	override : 'Portal.controller.ComponentFactory',
	getTools: function(portlet) {
        var me = this;
        return me.callSuper(arguments);
	}
});
//-------//TECHSUPP-1487 여기까지
//quartz 적용
Ext.define('Etna.override.app.bind.Multi',{
	override : 'Ext.app.bind.Multi',
	addObject : function(multiBindDescr, object, staticKeys){
		if(multiBindDescr.$skipBind){
			return false;
		}
		return this.callParent(arguments);
	}
});
Ext.define('Etna.override.app.ViewModel',{
	override : 'Ext.app.ViewModel',
	privates: {
		applyStores: function(stores){
			Ext.iterate(stores, function(key, value){
				if(value.proxy){
					value.proxy.$skipBind = true;
				}
			});
			this.callParent(arguments);
		}
	}
});
(function(){
	var scripts = document.getElementsByTagName("SCRIPT"),
		baseUrl = '/extjs/override.js';
	for(var i=0; i < scripts.length; i++){
		var src = scripts[i].src;
		if(src.lastIndexOf(baseUrl) > -1){
			baseUrl = src.substr(0, src.lastIndexOf(baseUrl));
			break;
		}
	}
	var origin = window.location.protocol + "//" + window.location.hostname + (window.location.port ? ':' + window.location.port : '');
	var contextPath = baseUrl.replace(origin , '');
	if(contextPath.length <= 1){
		contextPath = ' ';
	}
	Ext.data.Connection.templates = {
			api : 'api',
			contextPath : contextPath 
	};
})();
// quartz 적용


//[TECHSUPP-1642] - inputCover 클릭 시, 안쪽의 컴포넌트에 focus 가는 현상 - 적용해제
//Ext.define('Etna.override.form.field.plugin.InputCover', {
//	override : 'Etna.form.field.plugin.InputCover',
//	onCoverClick : function() {
//		var me = this,
//			cmp = me.getCmp();
//		
//		me.hideCover();
//		if(cmp.readOnly) {
//			return;
//		}
//		me.getCmp().focus();
//	}
//});


Ext.define('Etna.override.data.operation.Read', {
	override : 'Ext.data.operation.Read',
	config : {
		totalCount : undefined
	}
});

Ext.define('Etna.override.data.Store', {
	override : 'Ext.data.Store',
	
	config : {
		totalCountParam : true
	},
	
	totalCountParam : true,
	
	loadPage : function(page, options) {
		var me = this;
		if(me.getTotalCountParam()) {
			options = Ext.apply(options, {
				totalCount : me.getTotalCount()
			});
		}
		me.callParent(arguments);	
	}	
});

Ext.define('Etna.override.data.proxy.Direct', {
	override : 'Ext.data.proxy.Direct',

	getParams : function(operation) {
		var me = this,
			params = me.callParent(arguments),
			store = operation.getScope(),
			totalCount = operation.isReadOperation && Ext.isFunction(operation.getTotalCount) ? operation.getTotalCount() : undefined;
			
//		if(!store) {
//			Ext.Logger.error("store is not found");
//		}
		if(totalCount !== undefined) {
			params.totalCount = totalCount;
		}	
		return params;
	}
});





/**  
 * 외자 업체의 경우 포틀릿 메뉴바가 보이지 않도록 처리
 * 포탈 configContainer 나오지 않도록 함.
 * */
Ext.define('Portal.override.view.Portal', {
    override: 'Portal.view.Portal',
    initComponent: function() {
    	var me = this;
    	me.on('afterrender', me.onCustomeAfterRender, me, {
    		single: true
    	});
    	me.callParent(arguments);
    },
    
    onCustomeAfterRender: function(){
    	var me = this,
    	configContainer = me.lookupReference('configContainer');
    	var userType = Cmmn && Cmmn.User.data && Cmmn.User.data.userType || null; 
		if(!userType) {
			Ext.defer(function(arguments) {
				this.onCustomeAfterRender();
			}, 50, me);
			return false;
		}
		var pathname = document.location.pathname || ''; 
    	var overseaYn = pathname.indexOf('oversea.do') > -1;
		
		
		if(userType === 'External' && overseaYn) {
			configContainer.hide();
		}
    }
});





/*
 * 엠로 기술연구소 안성욱
 * Portal 드래그 앤 드랍 간혹 되지 않는 현상 해결
 */
Ext.define('Portal.override.view.PortalViewController',{
	override :'Portal.view.PortalViewController',
	setColumnWidths: function(widths) {
		var me = this;
		widths = Ext.isArray(widths) && widths.length === 0 ? [1] : widths;
		me.callParent([widths]);
	}
});


/*
 * 엠로 기술연구소 안성욱
 * Portal 컬럼 비율 연속적으로 변경 시(줄임)
 * Style 오류 발생하는 부분 해결 
 * etnajs 0.2.208 버전 반영 시 해당 오버라이드 소스 전체 제거 할 것(Etna.override.fx.target.Element)
 */
Ext.define('Etna.override.fx.target.Element',{
	override : 'Ext.fx.target.Element',
	setElVal : function(element, attr, value){
		var me = this;
		if(element.isDestroyed){
			return;
		}
		
		me.callParent(arguments);
	}
});


/** 서버 연결 에러메시지 한글화 */
Ext.define('Etna.override.direct.PollingProvider',{
	override : 'Ext.direct.PollingProvider',
	onData: function(opt, success, response) {
		var me = this, 
		    i, len, events;

		if (success) {
		    events = me.createEvents(response);
		    
		    for (i = 0, len = events.length; i < len; ++i) {
			me.fireEvent('data', me, events[i]);
		    }
		}
		else {
		    events = new Ext.direct.ExceptionEvent({
			data: null,
			code: Ext.direct.Manager.exceptions.TRANSPORT,
			message: "네트워크 상태가 불안정 합니다. <br/> 다시 시도해 주시길 바랍니다.",
			xhr: response
		    });
		    
		    me.fireEvent('data', me, events);
		}
	}
});


Ext.define('Ext.direct.RemotingProvider',{
	override : 'Ext.direct.RemotingProvider',
	onData: function(options, success, response) {
		var me = this,
		    i, len, events, event, transaction, transactions;
		    
		if (success) {
		    events = me.createEvents(response);
	
		    for (i = 0, len = events.length; i < len; ++i) {
			event = events[i];
			transaction = me.getTransaction(event);
			me.fireEvent('data', me, event);
	
			if (transaction && me.fireEvent('beforecallback', me, event, transaction) !== false) {
			    me.runCallback(transaction, event, true);
			    Ext.direct.Manager.removeTransaction(transaction);
			}
		    }
		}
		else {
		    transactions = [].concat(options.transaction);
		    
		    for (i = 0, len = transactions.length; i < len; ++i) {
				transaction = me.getTransaction(transactions[i]);
		
				if (transaction && transaction.retryCount < me.maxRetries) {
				    transaction.retry();
				}
				else {
				    event = new Ext.direct.ExceptionEvent({
						data: null,
						transaction: transaction,
						code: Ext.direct.Manager.exceptions.TRANSPORT,
						message: '네트워크 상태가 불안정 합니다. <br/> 다시 시도해 주시길 바랍니다.',
						xhr: response
				    });
		
				    me.fireEvent('data', me, event);
		
				    if (transaction && me.fireEvent('beforecallback', me, transaction) !== false) {
						me.runCallback(transaction, event, false);
						Ext.direct.Manager.removeTransaction(transaction);
				    }
				}
		    }
		}
	}
});

//TECHSUPP-1803
//scrollPaging 할 때, 화면 전체에 Lock 걸리는 기능
Ext.define('Site.override.toolbar.ScrollPaging', {
	override : 'Etna.toolbar.ScrollPaging',
	/**
	 * loadingTarget은 다음 페이지를 로딩할때 페이지 로딩이 걸릴 대상입니다.
	 * 로딩이 걸릴 대상의 우선순위는 다음과 같습니다.
	 * 1. loadingTarget프로퍼티에 지정된 대상
	 * 2. grid의 상위 컨테이너 중 controller를 포함하고 있는 view
	 * 3. grid 자신
	 * 우선 순위가 높은 대상을 못찾을 경우 다음 우선순위의 view가 target이 됨
	 * 예)
	 * 1번 대상이 없을경우 2번 대상이 loadingbar를 표현할 대상,
	 * 1번 대상이 없고 2번 대상도 없을 경우 3번 대상이 로딩 대상 
	 */
	loadingTarget : null,
	
	loadNextPage : function(lastSelection){
		var me = this, grid = me.getGrid(), store = grid.store;
		var target = me.loadingTarget || grid.up('[controller]') || grid;
		
		target.setLoading(true);
		grid.store.on({
			endupdate : function(){
				target.setLoading(false);
			},
			scope: me,
			single : true
		});
		
		grid.setLoading = Ext.emptyFn;
		me.callParent(arguments);
		delete grid.setLoading;
	},
	
	afterRender: function() {
		this.callParent();
		this.getEl().dom.tabIndex = -1;
	}
});

//그리드 칼럼목록에서 액션 컬럼의 경우 <i> Actions <i>보이는 현상 수정
Ext.define('Site.override.column.Action', {
	override : 'Ext.grid.column.Action',
	
	menuText : this.text
});

Ext.define('Ext.LazyItems', {
	extend: 'Ext.AbstractPlugin',
	alias: 'plugin.lazyitems',
	init: function(comp){
		this.callParent(arguments);
		
		if(this.eagerInstantiatioin){
			this.items = comp.prepareItems(this.items);
		}
		comp.beforeRender = Ext.Function.createInterceptor(comp.beforeRender, this.beforeComponentRender, this);
	},
	
	beforeComponentRender: function(){
		var me = this;
		Ext.defer(function(){ // 화면 전환 후, 컴포넌트를 추가하도록 함.
			me.cmp.add(me.items);
			delete me.cmp.beforeComponentRender;
			me.cmp.fireEvent('addedlazyitems');
		}, 1000);
	}
});

Ext.define('Etna.override.panel.Panel',{
	override :'Ext.panel.Panel',
	initConfig : function(config){
		var me = this;
		
		if(config.useLazyItems === true){

			var items = config.items;
			delete config.items;
			
			var plugin = {
	        	ptype: 'lazyitems',
	        	items: items
	        };
			
			if(!config.plugins ){
				config.plugins = plugin;
			}else if(Ext.isArray(config.plugins)){
				config.plugins.push(plugin);
			}else if(Ext.isObject(config.plugins)){
				var plugins = [plugin];
				plugins.push(config.plugins);
				config.plugins = plugins; 
			}
		}
		
		me.callParent([config]);
	}
});


Ext.define('Etna.override.grid.plugin.Export',{
	override :'Etna.grid.plugin.Export',
	init: function(grid) {
        var me = this,
            bind = grid.getBind();
            
        me.grid = grid;
        me.store = bind && bind.store ? bind.store.getValue() : grid.store;
        
        if (!me.store) {
        	Ext.defer(function(){
        		me.init(me.grid);
        	}, 1000);
        	return;
        }
        
        me.callParent(arguments);
    },
    
    pageSize : 10000,
	
	onExport : function(fileName)  {
		var me = this,
			paging = me.grid.down('pagingtoolbar, etnascrollpagingtoolbar'),
			exportHandler = function(prompt) {
				var value = prompt.down('form').getValues();
				value.split = me.split,
				prompt.close();
				me.renderingValue = value.rv;
				me.saveDocumentAs(value);
			},
			prompt = Ext.create('Ext.window.Window', {
				title : '#{다운로드}',
				width : 330,
				modal : true,
				closeAction : 'destroy',
				iconCls : 'btn-excel-download',
				bodyPadding : 10,
				resizable : false,
				items : [{
					xtype : 'form',
					layout : {
						type : 'vbox',
						align : 'stretch'
					},
					fieldDefaults : {
						labelSeparator : '',
						labelWidth : 70
					},
					items : [{
						xtype : 'textfield',
						fieldLabel : '#{파일명을 입력하세요.}',
						labelAlign : 'top',
						name : 'fileName',
						value : fileName || me.getExportFileName(),
						selectOnFocus : true,
						listeners : {
							boxready : function(field) {
								Ext.defer(field.focus, 10, this, [true]);
							},
							specialkey : function(field, e) {
								if(e.keyCode == e.ENTER) {
									exportHandler(prompt);
								}
							}
						}
					}, {
						xtype : 'radiogroup',
						fieldLabel : '#{유형}',
						items : [{ boxLabel: 'xlsx', name: 'type', inputValue: 'xlsx', checked : !me.defaultCsvExport},
						         { boxLabel: 'csv', name: 'type', inputValue: 'csv', checked : me.defaultCsvExport }]
					}, {
						xtype : 'radiogroup',
						fieldLabel : '#{범위}',
						hidden : !paging,
						items : [{ boxLabel: '#{현재페이지}', name: 'scope', inputValue: 'current', checked : !me.defaultPageAllExport},
						         { boxLabel: '#{전체페이지}', name: 'scope', inputValue: 'all', checked : me.defaultPageAllExport, disabled : !me.store.lastOptions }],
						listeners : {
							change : function(group, newValue, oldValue, e){
								var disabled = newValue.scope === 'all' ? false : true;
								group.ownerCt.down('combo{name ==="rowScope"}').setDisabled(disabled);
							}
						}
					},{
						xtype : 'combo',
						queryMode : 'local',
						fieldLabel : '#{행 범위}',
						displayField : 'range',
						name : 'rowScope',
						hidden : (me.store.getTotalCount() <= me.pageSize) || !paging,
						disabled : !me.defaultPageAllExport || !me.store.lastOptions,
						valueField : 'pageIndex',
						value : '0',
						editable : false,
						store :{
							fields : ['pageIndex', 'range'],
							data :(function(){
								var totalCount = me.store.getTotalCount(), datas = [], limit = me.pageSize;
								
								for(var i = 0, last = Math.ceil(totalCount/limit); i< last;i++){
									datas.push({
										pageIndex : i+'',
										range : Ext.String.format('{0} ~ {1}',(limit*i)+1, (limit*(i+1)) > totalCount ? totalCount : (limit*(i+1)))
									});
								}
								return datas;
							}())
						}
					}, {
						xtype : 'radiogroup',
						fieldLabel : '#{렌더링}',
						hidden : !me.useRenderer,
						items : [{ boxLabel: '#{사용}', name: 'rv', inputValue: true, checked : me.defaultRenderedValue },
						         { boxLabel: '#{미사용}', name: 'rv', inputValue: false, checked : !me.defaultRenderedValue }]
					}, {
						xtype : 'textfield',
						fieldLabel : '#{범위}',
						name : 'pageRange',
						emptyText : 'ex) 1-3 또는 1,3,5 또는 1-3,5,6',
						maskRe : /[0-9-,]/,
						stripCharsRe : /[ㄱ-힣]/,
						hidden : true
					}],
					dockedItems : [{
						xtype : 'toolbar',
						dock : 'bottom',
						style : {
							borderStyle : 'none'
						},
						items : ['->',{
							xtype : 'button',
							text : '#{확인}',
							width : 80,
							handler : function() {
								exportHandler(prompt);
							}
						}, {
							xtype : 'button',
							text : '#{취소}',
							width : 80,
							handler : function() {
								prompt.close();
							}
						},'->']
					}]
				}]
			});
		
		return prompt.show();
	},
	
	privates: {
		saveDocumentAs: function(config) {
            var me = this,
                provider = Etna.exporter.Manager.getProvider(config.type),
                isPaging = (config.scope == 'all');
            me.exportedData = {};
            var appender = provider.doExport({
                    fileName: config.fileName,
                    url: me.getUrl(),
                    params: me.getParams(),
                    delimiter: me.delimiter,
                    raisePerformance: me.raisePerformance,
                    sheets: [
                        {
                            xSplit: me.getXSplit(),
                            ySplit: me.getYSplit(),
                            sheetName: 'Sheet1',
                            metaDatas: me.getMetaDatas(),
                            headers: me.getHeaders(),
                            datas: isPaging ? null : me.getDatas()
                        }
                    ]
                }, isPaging);
            if (isPaging) {
                me.loadPageData(appender, config);
            }
        },
        loadPageData: function(appender,config) {
            var me = this,
                store = me.store,
                rowScopeIdx = Number(config.rowScope),
                totalPage = 1,
                totalCount = store.getTotalCount() < me.pageSize * (rowScopeIdx + 1) ? store.getTotalCount() % me.pageSize : me.pageSize,
                processor = Ext.Function.alias(me, 'process' + Ext.String.capitalize(me.proxy.type || me.proxy.config.type) + 'Proxy'),
                result = [],
                options;
            if (processor(totalPage, totalCount, appender) !== false) {
                me.requestCount = 0;
                Ext.Msg.show({
                    title: '#{잠시만 기다려 주십시오}',
                    msg: '#{데이터 요청중...}',
                    width: 300,
                    closable: false
                });
                
                options = {
                    action: 'read',
                    page: rowScopeIdx + 1,
                    limit: me.pageSize,
                    addRecords: false,
                    grouper: store.getGrouper(),
                    filters: store.getFilters().getRange(),
                    sorters: store.getSorters().getRange(),
                    params: Ext.apply((store.lastOptions ? store.lastOptions.params : {}), me.getParams())
                };
                operation = me.proxy.createOperation('read', options);
                me.proxy.read(operation);
            }
        }
		
	}
});

Ext.define('Etna.override.form.field.Date', {
    override: 'Ext.form.field.Date',
    checkChangeEvents: Ext.isIE && (!document.documentMode || document.documentMode <= 9) ? [
        'change',
        'keyup',
        'propertychange'
    ] : [
        'change',
        'keyup',
        'input',
        'dragdrop'
    ],
    valuePublishEvent: ['select', 'blur', 'change', 'specialkey']
});

/** TechSupp-2017 */
Ext.define('Site.override.grid.plugin.CellEditing', {
	override: 'Ext.grid.plugin.CellEditing',
	onCellClick: function(view, cell, colIdx, record, row, rowIdx, e){
		var columnHeader = view.ownerCt.getColumnManager().getHeaderAtIndex(colIdx);
		
		if(columnHeader && columnHeader.isEtnaCheckBoxColumn === true){
			return;
		}
		
		this.callParent(arguments);
	}
});



/** TechSupp-2017 */
Ext.define('Site.override.grid.column.Check', {
    override: 'Ext.grid.column.Check',
    
    // 신규추가된 부분. Etna에서 오버라이드 된 chekBox 컬럼이라는 플래그 값
    isEtnaCheckBoxColumn: true,
    
    processEvent: function(type, view, cell, recordIndex, cellIndex, e, record, row){
    	var me = this,
    		key = e.getKey();
    	
    	/** processEvent에 대한 오버라이드 소스가 있어도 해당 오버라이드를 무시하고,
    	    최초 선언 당시의 원본 함수를 호출함 */
    	var originalFn = arguments.callee.$previous;
    	while(originalFn.$previous){
    		originalFn = originalFn.$previous;
    	}
    	
    	originalFn.apply(me, arguments);
    	
    	if(me.editing){
    		if(type === 'mousedown') return;
    		me.editing = false;
    		if(!(key == e.ENTER || key == e.SPACE)){
    			var ePlugin = view.editingPlugin;
    			Ext.defer(me.startEdit, 1, me, [ePlugin, record]);
    		}
    	}
    },
    
    getEditor: function(record, defaultField){
    	var me = this,
    		view = me.getView(),
    		editingPlugin = view.editingPlugin,
    		field = editingPlugin.getColumnField(me, defaultField);
    	
    	if(field && !me.fieldListeners){
    		me.fieldListeners = field.on({
    			change: {
    				fn: function(){
    					var activeEditor = editingPlugin.getActiveEditor(),
    						activeRecord = editingPlugin.getActiveRecord();
    					
    					if(activeEditor){
    						// http://alm.emro.co.kr/browse/TECHSUPP-996
    						if(activeEditor && activeEditor.completeEdit && activeEditor.completeEdit.$emptyFn === true){
    							delete activeEditor.completeEdit;
    						}
    						
    						editingPlugin.completeEdit(true);
    						me.startEdit(editingPlugin, activeRecord);
    					}
    				},
    				buffer: 1
    			},
    			click: function(e){
    				var inputEl = e.getTarget('input');
    				
    				if(!inputEl){
    					field.onBoxClick.call(field);
    				}
    			},
    			mousedown: function(e){
    				e.preventDefault();
    				field.focus(false, 1);
    			},
    			element: 'bodyEl',
    			destroyable: true
    		});
    	}
    	
    	return field;
    }
});

Ext.define('Mdi.view.override.mdi.Left', {
    override: 'Mdi.view.mdi.Left',
    columns: [
              {
                  xtype: 'treecolumn',
                  renderer: function(value, metaData, record, rowIndex, colIndex, store, view) {
                      if (record.isLeaf()) {
                          metaData.tdCls += ' leaf-node';
                          if (record.previousSibling && !record.previousSibling.hasChildNodes()) {
                              metaData.tdCls += ' nbr-node';
                          }
                      } else {
                          metaData.tdCls += ' parent-node';
                      }
                      if (record.isLast()) {
                          metaData.tdCls += ' last-node';
                      } else if (record.isFirst()) {
                          metaData.tdCls += ' first-node';
                      }
                      metaData.tdCls += ' menu-level-' + record.get('depth');
                      return Ext.String.format('#{' + value + '}');
                  },
                  dataIndex: 'text',
                  flex: 1
              }
          ]
});
Ext.define('Mdi.view.override.mdi.LeftViewController', {
	override: 'Mdi.view.mdi.LeftViewController',
	init: function() {
		if(MdiManager.spmain) {
			this.getView().hide();
		}
		this.callParent(arguments);
	},
	setMenu: function(menuData) {
		var me = this, view = me.getView();
		me.callParent(arguments);
		
		// Left 메뉴 강제 다국어 처리
		view.setTitle(Ext.String.format('#{'+view.getTitle()+'}'));
	}
});

Ext.define('Mdi.view.override.mdi.Top', {
    override: 'Mdi.view.mdi.Top',
    items: [
            {
                xtype: 'container',
                /*스킵메뉴 미제공  pdf#39 김형민 xtype toolbar에서 container로 변경*/
                anchor: '100%',
                reference: 'top',
                height: 45,
                ui: 'mdi-top',
                focusable: true,
                layout: {
                    type: 'hbox',
                    align: 'middle'
                },
                style: {
                    'border-bottom': 'none'
                },
                focusable: true,
                tabIndex: 1,
                listeners: {
                	focus: function() {
                		var buttonEl = this.query('button[cls=skip-button]')[0];
                		buttonEl.setHidden(false); 
                		buttonEl.focus();
                	}
                },
                items: [
                    {
                     	xtype: 'button',
                     	cls: 'skip-button',
                     	hidden: true,
                     	text: '#{본문 바로가기}',
                     	style: 'position: fixed !important;left:3px !important;right:auto;margin:0px;z-index:100;',
                     	handler: function() {
                     		if(MdiManager.mdiTab.hidden) {
                     			var spmain = MdiManager.spmain.el.query('iframe')[0];
                     			spmain.focus();
                     			spmain.contentDocument.querySelector('a').focus();
                     		} else {
                     			var activeTab = MdiManager.mdiTab.activeTab;
                     			if(activeTab) {
                     				if (activeTab.layout && activeTab.layout.config.type === 'card') {
                     					activeTab = activeTab.layout.activeItem;
                     				} else if(activeTab.id.indexOf('sitemap') != -1) {
	                    				activeTab.body.query('dt')[0].focus();
		                    		    return;
		                    		}
                     				/*if(activeTab.getLayout().type === 'card') {
                     					var currentItem = activeTab.getLayout().activeItem;
                     					var currentComp = currentItem.items.items[0];
                     					var isForm = currentComp.xtype==='form';
                     					
                     					if(isForm) {
                     						currentComp.items.items[0].focus();
                     						return;
                     					}
                     					currentComp.focus();
                     					return;
                     				}*/
                     				var item = activeTab.query('tab[hidden=false], textfield[hidden=false], button[hidden=false], datefield[hidden=false], checkbox[hidden=false], numberfield[hidden=false], textarea[hidden=false], radio[hidden=false], etnaattachmentfield[hidden=false], combo[hidden=false]')[0];
                     				if(!item && activeTab.el.query("iframe")[0]) {
                     					var targetIframe = activeTab.el.query("iframe")[0];
                     					targetIframe.focus();
                     					var aTags = targetIframe.contentDocument.querySelectorAll('a');
                     					for(var i=0; i<aTags.length; i++) {
                     						if(aTags.tabIndex != -1) {
                     						    aTags[i].focus();	
                     						    return;
                     						}
                     					}
                     				}
                     				item.focus();
                     			}
                     		}
                     	},
                     	listeners: {
                     		blur: function() {
                     			this.setHidden(true);
                     		}
                     	}
                     },
                	{
                        xtype: 'button',
                        cls: 'mdi-top-logo',
                        id : 'kepco-mdi-logo-button', //logo 버튼의 아이디를 unique한 아이디로 지정
                        margin : '0 0 0 10',
                        width : 300,
                        height : 18,
                        ui : 'plain',
                        tooltip: 'KEPCO | 전달조달시스템 메인화면 이동',
                        tooltipType: 'title',
                        focusable: true,
                        listeners : {
                        	click : 'onLogoClick'
                        }
                    }, 
                    {
                    	xtype: 'button',
                    	cls: 'mdi-top-logo_buyer',
                    	id : 'kepco-mdi-logo-button2',
                    	hidden : true,
                    	margin : '0 0 0 00',
                    	width : 62,
                    	height : 18,
                    	ui : 'plain',
                    	tooltip: 'KEPCO | 전달조달시스템 메인화면 이동',
                    	tooltipType: 'title',
                    	focusable: true,
                    	listeners : {
                    		click : 'onLogoClick'
                    	}
                    }, 
                    {
                        xtype: 'label',
                        reference: 'mdiRepresentativeTelNo',
                        text: '#{업무안내(대표전화) : 061-345-1247,9}',
                        style: {
                        	fontSize: '15px'
                        }
                    }, 
                    {
                        xtype: 'tbspacer',
                        width: 20
                    },
                    {
                         xtype: 'tbfill'
                    },
                    {
                        xtype: 'textfield',
                        width: 420,
                        fieldLabel: '#{통합검색}',
                        enableKeyEvents: true,
                        listeners: {
                            keydown: 'onTextfieldKeydown'
                        },
                        triggers: {
                            mytrigger: {
                                handler: function(field, trigger, e) {
                                	var value = field.value;
                            	    if(value === null || value === undefined || value.trim() === '') {
                            	           Etna.Message.alert('#{검색어를 입력해주세요.}');
                            	           field.setValue('');
                            	           return;
                            	     }
                                    field.up('[controller]').settingLeftSearchMenu(value);
                                    field.setValue('');
                                },
                                cls: 'trigger-search'
                            }
                        },
                        tooltip: '통합검색'
                    },
//                    {
//                        xtype: 'component',
//                        reference: 'mdiTopSeparator1',
//                        cls: 'mdi-functionbar-separator'
//                    },
/*                    {
	                    xtype: 'button',
	                    //스킵메뉴 미제공  pdf#39 김형민
	                    ui: 'mdi-status-quick-button-small',
	                    text : '#{본문바로가기}',
	                    tooltip: '#{본문 내용으로 포커스 이동}',
	                    tooltipType: 'title',
	                    handler : function(){
	                    	var activeTab = MdiManager.mdiTab.activeTab;
	                    	if(activeTab){
	                    		if(activeTab.id.indexOf('sitemap') != -1) {
	                    			activeTab.body.query('dt')[0].focus();
	                    		    return;
	                    		}
	                    		if(Ext.query('.spmain').length !== 0) {
									Ext.query('.spmain')[0].querySelector('iframe').contentDocument.querySelector('a[title=이전배너보기]').focus();
									return;
								}
	                    		activeTab.query('textfield, button')[0].focus();
	                    	} else {
	                    		if(Ext.query('.spmain').length !== 0) {
									Ext.query('.spmain')[0].querySelector('iframe').contentDocument.querySelector('a[title=이전배너보기]').focus();
									return;
								}
	                    	}
	                    }
	                },*/
//	                {
//                        xtype: 'component',
//                        reference: 'mdiTopSeparator2',
//                        cls: 'mdi-functionbar-separator'
//                    },
                    {
                        xtype: 'tbfill'
                    },
                    {
                        xtype : 'button',
                        text : '#{로그아웃}',
                        ui: 'mdi-status-quick-button-small',
                        bind : {
                        	hidden : '{!authenticated}'
                        },
                        tooltip: '#{페이지 이동}',
                        tooltipType: 'title',
                        listeners: {
                            click: 'onMdiLogoutButtonClick'
                        }
                    },
                    {
                        xtype: 'component',
                        reference: 'mdiTopSeparator3',
                        cls: 'mdi-functionbar-separator',
                    	bind : {
                        	hidden : '{!authenticated}'
                        }
                    },
//                    {
//                        xtype : 'button',	
//                        text : '#{디지털도우미}',
//                        reference: 'mdiChatbotButton',
//                        ui: 'mdi-status-quick-button-small',
//                        style:{
//                        	fontWeight:'bold'
//                        },
//                        cls : 'mdi-quick-button-lock-user-manual',
//                        listeners: {
//                            click: 'onCallChatbotButtonClick'
//                        },
//                        tooltip: '새창열림',
//                        tooltipType: 'title'
//                    },
//                    {
//                        xtype: 'component',
//                        reference: 'mdiTopSeparator4',
//                        cls: 'mdi-functionbar-separator'
//                    },
                    {
                        xtype : 'button',
                        text : '#{로그인}',
                        ui: 'mdi-status-quick-button-small',
                        cls : 'mdi-quick-button-lock',
//                        iconCls : 'mdi-quick-button-lock-icon',
                        bind : {
                        	hidden : '{authenticated}'
                        },
                        tooltip: '#{팝업 열림}',
                        tooltipType: 'title',
                        listeners: {
                                    click: 'onMdiCertLogInButtonClick'
                        }
                    },
                    {
                        xtype: 'component',
                        reference: 'mdiTopSeparator5',
                        cls: 'mdi-functionbar-separator',
                        bind : {
                        	hidden : '{authenticated}'
                        }
                    },
                    {
                        xtype : 'button',
                        text : '#{ID/비밀번호찾기}',
                        ui: 'mdi-status-quick-button-small',
                        bind : {
                        	hidden : '{authenticated}'
                        },
                        tooltip: '#{페이지 이동}',
                        tooltipType: 'title',
                        listeners: {
                                    click: 'onMdiFindIdPwButtonClick'
                        }
                    },
                    {
                        xtype: 'component',
                        reference: 'mdiTopSeparator6',
                        cls: 'mdi-functionbar-separator',
                        bind : {
                        	hidden : '{authenticated}'
                        }
                    },
                    {
                        xtype : 'button',
                        text : '#{회원가입}',
                        ui: 'mdi-status-quick-button-small',
                        bind : {
                        	hidden : '{authenticated}'
                        },
                        tooltip: '#{페이지 이동}',
                        tooltipType: 'title',
                        listeners: {
                            click: 'onMemberJoinButtonClick'
                        }
                    },
//                    {
//                        xtype: 'component',
//                        reference: 'mdiTopSeparator7',
//                        cls: 'mdi-functionbar-separator',
//                        bind : {
//                        	hidden : '{authenticated}'
//                        }
//                    },
                    {
                        xtype: 'button',
                        ui: 'mdi-status-quick-button-small',
                        reference: 'mdiUsernameButton',
                        bind: {
                            hidden: '{!authenticated}',
                            text: '{mdiUserName}'
                        },
                        tooltip: '#{페이지 이동}',
                        tooltipType: 'title',
                        listeners: {
                            click: 'onUserNameButtonClick'
                        }
                    },
                    {
                        xtype: 'component',
                        reference: 'mdiTopSeparator8',
                        cls: 'mdi-functionbar-separator',
                        bind : {
                        	hidden : '{!authenticated}'
                        }
                    },
                    {
                        xtype : 'button',
                        reference: 'mdiSettingButton',
                        text : '#{설정}',
                        ui: 'mdi-status-quick-button-small',
                        iconAlign : 'right',
                        iconCls : 'mdi-quick-button-settings-icon',
                        arrowVisible: false,
                        tooltip: '#{Personal Setup}',
                        tooltipType: 'title',
                        menu: {
                            xtype: 'menu',
                            items: [
                                {
                                    xtype: 'menuitem',
                                    reference: 'localeSetting',
                                    text: '#{언어}'
                                },
                                {
                                    xtype: 'menuitem',
                                    text: '#{다국어 설정}',
                                    bind: {
                                        hidden: '{!authenticated}'
                                    },
                                    listeners: {
                                        click: 'onLocaleConfigurationClick'
                                    }
                                }
                            ]
                        }
                    },
                    {
                        xtype: 'tbspacer',
                        width: 20
                    },
                    {
                    	xtype: 'button',
                    	ui: 'mdi-status-quick-button-small',
                    	style:{
                        	fontWeight:'bold'
                        },
                        cls : 'mdi-quick-button-lock-user-manual',
                        tooltip: '#{페이지 이동}',
                        tooltipType: 'title',
                        listeners: {
                        	click : 'openSiteMap'
                        }
                    },
                    {
                		xclass : 'CmmnMdi.view.mdi.KepcoLogin',
                		reference : 'KepcoLoginRef',
                		lazy : true,
                		modal : true,
                		draggable : true,
                		floating : true,
                		closable : false,
                		closeAction : 'hide',
                		listeners: {
                			showCertToolkit: 'showCertToolkit'
                		}
                	}
                ]
            },
            {
                xtype: 'toolbar',
                anchor: '100%',
                reference: 'menuBar',
                border: 0,
                cls: 'mdi-top-menu',
                padding: 0,
                ui: 'mdi-top-menubar',
                height : 60,
                defaults: {
                    arrowVisible: false,
                    ui: 'mdi-top-menu-button-small',
                    height: 60,
                    enableToggle: true,
                    toggleGroup: 'mdiTopMenu',
                    allowDepress: false
                },
                enableOverflow: true,
                overflowHandler: 'scroller'
            }, {
                xtype: 'toolbar',
                anchor: '100%',
                height : 28,
                border : '0 0 1 0',
                ui: 'mdi-status',
                reference : 'breadcrumbBar',
                layout : {
                    type : 'hbox',
                    align : 'stretch'
                },
                items: [
                    {
                        xtype: 'container',
                        flex: 1,
                        cls: 'mdi-homebar',
                        layout: {
                            type: 'hbox',
                            align: 'middle'
                        },
                        items: [                                                
                            {
                                xtype: 'button',
                                ui: 'mdi-status-quick-button-small',
                                iconCls: 'mdi-topmenu-openhome',
                                tooltip: '#{홈 탭으로 이동 버튼}',
                                tooltipType: 'title',
                                padding : '3 10 3 15',
                                listeners: {
                                    click: 'onHomeButtonClick'
                                }
                            },
                            {
                                xtype: 'breadcrumb',
                                reference: 'menuBreadcrumb',
                                cls: 'mdi-breadcrumb',
                                buttonUI: 'mdi-breadcrumb-button-toolbar-small',
                                displayFieldName: 'text',
                                showIcons: false,
                                layout: {
                                    type: 'hbox',
                                    align: 'stretch'
                                },
                                bind: {
                                    store: '{menuStore}'
                                },
                                listeners: {
                                    selectionchange: 'onBreadcrumbSelectionChange'
                                }
                            }
                        ]
                    },
                    {
                        xtype: 'button',
                        reference: 'topToggleButton',
                        margin: 0,
                        width : 28,
                        height : 28,
                        ui: 'mdistatus-togglebutton-small',
                        enableToggle: true,
                        iconCls: 'mdi-top-toggle-icon',
                        tooltip: '#{상단 메뉴 접기}',
                        tooltipType: 'title',
                        listeners: {
                            click: 'onTopToggleButtonClick'
                        }
                    }
                ]
            }
        ]
});

Ext.define('Mdi.view.override.mdi.ViewportViewModel', {
    override: 'Mdi.view.mdi.ViewportViewModel',
    data: {
    	buyerlogo: false,
    },
});

Ext.define('Mdi.view.override.mdi.TopViewController', {
    override: 'Mdi.view.mdi.TopViewController',
    
    spHiddenComponents: [
        'mdiTopSeparator1',
    	'mdiChatbotButton',
    	'mdiSettingButton',
    	'mdiRepresentativeTelNo'
    ],
    
    init: function(){
    	var me = this,
    		view = me.getView(),
    		vm   = me.getViewModel();
    	
    	if(MdiManager.spmain) {
    		view.lookupReference('breadcrumbBar').hide();
    	}
    	view.on('afterrender', me.onAfterRender, me, {single:true});
    	me.callParent(arguments);
    	view.settingLeftSearchMenu = Ext.Function.bind(me.onSettingLeftSearchMenu, me);
    	view.openSiteMap = Ext.Function.bind(me.openSiteMap, me);
    	
    	Etna.onDone(function() {
    		if(Cmmn.User.data && Cmmn.User.data.userType === 'Internal') {
    			var buttonEl = view.query('button[cls=mdi-top-logo_buyer]')[0];
        		buttonEl.setHidden(false);
        		
	    		//var logoId = document.getElementById('kepco-mdi-logo-button');
	    		//logoId.className = logoId.className.replace("mdi-top-logo","mdi-top-logo_buyer");
	    		//logoId.classList.replace("mdi-top-logo","mdi-top-logo_buyer");
	    		//logoId.style.backgroundImage = "url(/resources/css/images/custom/logo_buyer.svg) !important";
	    	} else {
	    		var buttonEl = view.query('button[cls=mdi-top-logo_buyer]')[0];
        		buttonEl.setHidden(true);
	    		//vm.set("buyerlogo", false);
	    	}
        });
    },
    
    openSiteMap: function() {
    	var me = this,
	    view = this.getView(),
	    viewportController = view.up('mdiviewport').controller;
	    menu = Mdi.store.Menu.getRoot().findChild('text','사이트맵', true);

        viewportController.onMdiTopOpenMenu(menu);
    },
    
    onSettingLeftSearchMenu: function(value) {
    	var view = this.getView();
        var viewPort = view.up('mdiviewport');
        var viewPortController = viewPort.controller;
        var menus = Mdi.store.Menu.getRoot().childNodes;
        
        var hasSearchMenu = false;
        for(var i=0; i<menus.length; i++) {
        	if(menus[i].get('id').indexOf('SEARCH') != -1) {
        		hasSearchMenu = true;
        	}
        };
        
        if(!hasSearchMenu) {
        	Etna.Message.alert('#{검색 권한이 없습니다.}');
        	return;
        }
        
        
        MdiManager.search.keyword = value;
        
        MdiManager.search.load = function() {
        	var search = viewPort.lookupReference('search');
         	search.controller.load({
         		menuData: MdiManager.search.currentMenu,
                keyword: MdiManager.search.keyword
         	})
        }
        
        
        
        for(var i=0; i<menus.length; i++) {
        	if(menus[i].get('id').indexOf('SEARCH') != -1) {
        		viewPortController.onMdiTopOpenMenu(menus[i].childNodes[0]);
        	}
        };
		/*	
        var firstChild = MdiManager.search.rootMenu.childNodes[0];
        MdiManager.search.currentMenu = firstChild.getId();
        MdiManager.search.oldMenu = firstChild.getId();*/
    },
    
    onAfterRender: function(){
    	var me = this, el,
    		usernameBtn = me.lookupReference('mdiUsernameButton');
    	
    	/** oversea.do 호출 시, 상단 탭의 컴포넌트 숨김처리. (spHiddenComponents : 제거대상 컴포넌트) */
    	if(MdiManager && MdiManager.spmain){
			Ext.each(me.spHiddenComponents, function(candidate){
    			var hiddenCandidate = me.lookupReference(candidate);
    			
    			if(hiddenCandidate){
    				hiddenCandidate.setHidden(true);
    			}
    		});
			
                                                                                                                                                                                                           	    	/** 사용자명 클릭 Disable 처리 */
			if(usernameBtn){
				el = usernameBtn.getEl();
				if(el){
					el.dom.style.pointerEvents = 'none';
				}
			}
    	}
    },
    
    onCallChatbotButtonClick : function(){
    	var width = 500;
    	var height = 720;
    	var leftPosition = (screen.width-width) / 1.5;
    	var topPosition = (screen.height-height) / 2.5;
    		
    	window.open('about:blank', 'callChatbot', 'location=no,scrollbars=yes,menubar=no,width='+width+',height='+height+',top='+topPosition+',left='+leftPosition);
    			
    	var frm = Site.util.Format.makeForm('resources/popup/html/pop_chatbot.html', 'POST',  'callChatbot');
    	frm.appendChild(Site.util.Format.makeInput('hidden', Ext.query("meta[name='_csrf_parameter']")[0].content,Ext.query("meta[name='_csrf']")[0].content));
    	document.body.appendChild(frm);
    	frm.submit();
    },
    
    
       
    
    
    
    
    createMenuItems: function(childNodes) {
        var me = this,
            menuItems = [];
        
        menuItems = me.callParent(arguments);
        
        Ext.Array.each(menuItems, function(item){
            // Top 메뉴 강제 다국어 처리
           item.text = Ext.String.format('#{'+item.text+'}');
        });
        
        return menuItems;
    },
    
    initMenuBar: function(menus) {
        var me = this;
            menuBar = me.lookupReference('menuBar'),
            items = [];
        
        me.callParent(arguments);
        
        items = menuBar.items;
        Ext.Array.each(items.getRange(), function(item){
            // Top 메뉴 강제 다국어 처리
           item.setText( Ext.String.format('#{'+item.getText()+'}') );
        });
    },
    // 다국어 설정 버튼
    onLocaleConfigurationClick: function(item, e, eOpts) {
         var me = this, view = me.getView();
         view.fireEvent('i18nEdit');
     },

     onTextfieldKeydown: function(textfield, e, eOpts) {
    	if(e.keyCode === 13) {
    		var value = textfield.value;
    	    if(value === null || value === undefined || value.trim() === '') {
    	           Etna.Message.alert('#{검색어를 입력해주세요.}');
    	           textfield.setValue('');
    	           return;
    	     }
    		 this.onSettingLeftSearchMenu(value);
    		 textfield.setValue('');
         }
     }
});

Ext.define('Mdi.view.override.mdi.I18nEditor', {
    override: 'Mdi.view.mdi.I18nEditor',
    dockedItems: [
          {
              xtype: 'toolbar',
              dock: 'top',
              items: [
                  {
                      xtype: 'combobox',
                      reference: 'localeCombobox',
                      fieldLabel: '#{locale}',
                      displayField: 'value',
                      forceSelection: true,
                      queryMode: 'local',
                      valueField: 'key',
                      bind: {
                          value: '{locale}',
                          store: '{localeStore}'
                      },
                      listeners: {
                          change: 'onLocaleChange'
                      }
                  },
                  {
                      xtype: 'tbspacer',
                      flex: 1
                  },
                  {
                      xtype: 'button',
                      itemId: 'addButton',
                      text: '#{add}',
                      listeners: {
                          click: 'onAddButtonClick'
                      }
                  },
                  {
                      xtype: 'button',
                      itemId: 'saveButton',
                      text: '#{save}',
                      listeners: {
                          click: 'onSaveButtonClick'
                      }
                  },
                  {
                      xtype: 'button', // Close 버튼 추가
                     itemId: 'closeButton',
                      text: '#{close}',
                      listeners: {
                          click: function(component){
                              var me = this;
                              mdii18neditor = this.up('mdii18neditor');
                              mdii18neditor.close();
                          }
                      }
                  }
              ]
          }
      ]
});

Ext.define('Mdi.view.override.mdi.ViewportViewController', {
    override: 'Mdi.view.mdi.ViewportViewController',
    init: function() {
    	if(MdiManager.spmain) {
    		this.getView().lookupReference('mdiTabPanel').hide();
    		this.getView().lookupReference('tools').hide();
    	}
    	this.callParent(arguments);
    },
    
    onMdiTopI18nEdit: function(eventOptions) {
        var me = this,
            tabpanel = me.lookupReference("mdiTabPanel"),
            activeTab = tabpanel.getActiveTab();
        
        var editor = Ext.create('Mdi.view.mdi.I18nEditor', {
            reference: 'mdiI18nEditor',
            floating: true,
            closeAction: 'hide',
            region: 'east'
        });
        
        editor.show();
        editor.load(activeTab.classpath);
    },
    onMdiLeftOpenMenu: function(menu, eventOptions) {
        var me = this, vm = me.getViewModel(), classpath = menu.get('classpath');
        
        var addOrShow = function(){
            if(MdiManager.hasView(classpath)) {
                MdiManager.showView(classpath);
                if(menu.get('code').indexOf('SEARCH') !== -1) {
                	MdiManager.search.currentMenu = menu;
                	MdiManager.search.load();
                }
            }else {
            	if(menu.get('code').indexOf('SEARCH') !== -1) {
            		MdiManager.search.currentMenu = menu;
                    MdiManager.addView(classpath, {
						title : Ext.String.format('#{통합검색}'),
						authKey : menu.get('code')
					}, menu.get('requireClass'), MdiManager.search.load);
					return;
            	};
            	
                MdiManager.addView(classpath, {
                    title : Ext.String.format('#{'+menu.get('text')+'}'),
                    authKey : menu.get('code')
                }, menu.get('requireClass'));
            }
        };
        if(menu.isLeaf()){
            addOrShow();
        }
    },
    onMdiTopOpenMenu: function(menu, eventOptions) {
        var me = this, vm = me.getViewModel(), classpath = menu.get('classpath'), mdiLeft = me.lookupReference('mdiLeft');
        
        var addOrShow = function(){
            if(MdiManager.hasView(classpath)) {
            	if(menu.get('code').indexOf('SEARCH') !== -1) {
                	MdiManager.search.currentMenu = menu;
            		MdiManager.closeView(classpath);
            		MdiManager.addView(classpath, {
						title : Ext.String.format('#{통합검색}'),
						authKey: menu.get('code')
					}, menu.get('requireClass'), MdiManager.search.load);
                	return;
                }
            	MdiManager.showView(classpath);
            }else {
            	if(menu.get('code').indexOf('SEARCH') !== -1) {
            		MdiManager.search.currentMenu = menu;
                    MdiManager.addView(classpath, {
						title : Ext.String.format('#{통합검색}'),
						authKey: menu.get('code')
					}, menu.get('requireClass'), MdiManager.search.load);
					return;
            	}
                MdiManager.addView(classpath, {
                    title : Ext.String.format('#{'+menu.get('text')+'}'),
                    authKey : menu.get('code')
                }, menu.get('requireClass'));
            }
        };
        if (vm.get('withLeftMenu')) {
            if (menu.isLeaf()) {
                addOrShow();
            } else {
                if(!mdiLeft.isHidden()){
                	mdiLeft.setMenu(menu);
                }
            }
            if(MdiManager.spmain){
	    		return true;
	    	}
            return false;
        } else if (menu.isLeaf()) {
            addOrShow();
            if(MdiManager.spmain){
	    		return true;
	    	}
        }
    }
});

Ext.define('Ext.toolbar.override.Breadcrumb', {
	override: 'Ext.toolbar.Breadcrumb',
	
	updateSelection: function(node) {
		var me = this;
		me.callParent(arguments);
		
		Ext.each(this._buttons, function(button) {
			var text = button.getText(),
				menu = button.menu;
			
			if(text) {
				button.setText(Ext.String.format('#{' + text + '}'));
			}
			if(button.el && button.el.dom.querySelector('.x-btn-split-right')) {
				text = button.getText();
				button.el.dom.querySelector('.x-btn-split-right').setAttribute('title',  (text ? text+' ' : '')+Ext.String.format('#{하위 메뉴 선택 버튼}'));
			}
			
			menu.un('beforeshow', me.onBeforeShow);
			menu.on('beforeshow', me.onBeforeShow, menu);
		});
	},
	
	onBeforeShow: function(menu) {
		if(menu.items) {
			Ext.each(menu.items.getRange(), function(item) {
				var text = item.text;
				if(text) {
					item.setText(Ext.String.format('#{' + text + '}'));
				}
			});
		}
	}
	
});

//TECHSUPP-1907
//프로그래바 클릭 후 팝업화면 조회시 속도개선
Ext.define('Ext.util.Floating', {
	override: 'Ext.panel.Panel',
	toFront: function(preventFocus) {
		var me = this;
		
		if(!me.modal) {
			if(me.zIndexManager.bringToFront(me, preventFocus || !me.focusOnToFront)) {
				if(me.hasListeners.tofront) {
					me.fireEvent('tofront', me, me.el.getZIndex());
				}
			}
		}
		return me;
	},
	
	onFloatShow:function() {
		var me = this;
		
		if(me.needsCenter) {
			me.center();
		}
		
		delete me.needsCenter;
		
		if(me.toFrontOnShow) {
			var preventFocus = false;
			
			if(me.zIndexManager.bringToFront(me, preventFocus || !me.focusOnToFront)) {
				if(me.hasListeners.tofront) {
					me.fireEvent('tofront', me, me.el.getZIndex());
				}
			}
		}
	}
});

Ext.define('Ext.ZIndexManager', {
	override: 'Ext.ZIndexManager',
	onComponentUpdate:function(comp) {
		if(!comp.modal) {
			if(this.zIndexStack.contains(comp)) {  
				this.zIndexStack.sort();
			}
		}
	}
});


Ext.define('Etna.toolbar.override.TreeFinder', {
	override: 'Etna.toolbar.TreeFinder',
	
	getToolbarItems: function() {
		var me = this;
		
		var columnField = {
			xtype : 'combobox',
			action : 'columnSelect',
			store : Ext.create('Ext.data.Store',{
				fields : ['dataIndex','text','xtype'] 
			}),
			valueField : 'dataIndex',
			displayField : 'text',
			forceSelection : true,
			editable : false,
			multiSelect : true,
			matchFieldWidth : false,
			growMax : 200,
			growMin : 100,
			grow : true,
			queryMode : 'local'
		};
		var textField = Ext.apply(me.fieldCfg || {}, {
			action : 'keyword',
			allowBlank : false,
			listeners: {
				scope : me,
				blur : 'onTextFieldBlur',
                specialKey: 'onTextFieldSpecialKey'
            }
		});
		textField = Ext.applyIf(textField, {
			xtype: 'textfield',
			width : 100,
			enforceMaxLength: true,
            maxLength: 30,
			fieldLabel : me.fieldLabel
		});
		
		var searchButton = Ext.apply(me.searchButtonCfg || {}, {
			action : 'search',
			handler:  me.doSearch,
			scope: me
		});
		searchButton = Ext.applyIf(searchButton, {
			xtype: 'button',
			iconCls : me.searchButtonIconCls
		});
		
		var previousButton = Ext.apply(me.previousButtonCfg || {}, {
			action : 'previous',
			handler:  me.onPreviousButtonClick,
			scope: me,
			disabled : true
		});
		previousButton = Ext.applyIf(previousButton, {
			xtype: 'button',
			iconCls : me.previousButtonIconCls
		});
		
		var nextButton = Ext.apply(me.nextButtonCfg || {}, {
			action : 'next',
			handler:  me.onNextButtonClick,
			scope: me,
			disabled : true
		});
		nextButton = Ext.applyIf(nextButton, {
			xtype: 'button',
			iconCls : me.nextButtonIconCls
		});
		return [columnField, textField, searchButton, previousButton, nextButton, 
		{
            xtype: 'tbtext',
            action: 'display'
        }];
	},
	doSearch : function(){
		var me = this;
		var field = me.getSearchTextField();
		if(field.validate()){
			var keyword = field.getValue();
			me.search(keyword);
			me.updateInfo();
		} else {
			Etna.Message.alert('#{검색조건이 유효하지 않습니다.}');
		}
	}
});

/** 크롬에서 브라우저 글꼴크기를 조정시 checkboxmodel이 깨지는 현상 처리 */
Ext.define('Ext.selection.CheckboxModel', {
	override: 'Ext.selection.CheckboxModel',
	constructor: function(){
		var me = this;
		if(Ext.isChrome){
			var _checkSelectorCss = document.createElement('style');
			_checkSelectorCss.innerHTML = me.checkSelector+" {height:auto !important}";
			document.body.appendChild(_checkSelectorCss);
		}
		me.callParent(arguments);
	}
});

/** numberField에서 readOnly시 복사안되는 현상 수정*/
Ext.define('Etna.form.field.plugin.InputCover', {
    override: 'Etna.form.field.plugin.InputCover',
    onCoverClick: function() {
        var me = this;
        
        if(me.getCmp().readOnly){
        	return;
        }
        me.callParent();
    }
});

/** (공사용역)합동테스트 결과 오류 및 개선 내역 No.34 일괄삭제 기능 구현 요청 */
Ext.define('Etna.override.grid.column.Eliminate', {
    override: 'Etna.grid.column.Eliminate',
    showHeaderCheckbox: false,
    isHeaderCheck: false,
    sortable: false,
    initComponent: function(){
    	
    	var me = this;
    	
    	if(me.showHeaderCheckbox){
    		me.renderTpl = [
                '<div id="{id}-titleEl" data-ref="titleEl" {tipMarkup}class="', Ext.baseCSSPrefix, 'column-header-inner',
                    '<tpl if="empty"> ', Ext.baseCSSPrefix, 'column-header-inner-empty</tpl>">',
                    '<div id="{id}-checkEl" style="float:left; cursor:pointer;" class="'+Ext.baseCSSPrefix+'grid-checkcolumn"></div>',
                    '<span id="{id}-textEl" data-ref="textEl" class="', Ext.baseCSSPrefix, 'column-header-text',
                        '{childElCls}">',
                        '{text}',
                    '</span>',
                    '<tpl if="!menuDisabled">',
                        '<div id="{id}-triggerEl" data-ref="triggerEl" role="presentation" class="', Ext.baseCSSPrefix, 'column-header-trigger',
                        '{childElCls}" style="{triggerStyle}"></div>',
                    '</tpl>',
                '</div>',
                '{%this.renderContainer(out,values)%}'
            ];
    		me.on('afterrender', me.onAfterRender, me, {
    			single : true
    		});
    	}
    	me.callParent(arguments);
    },
    
    onAfterRender: function(){
    	
    	var me = this,
    		checkDiv = me.getHeaderCheckDiv();
    		
    	checkDiv.on('click', me.onHeaderCheckHandler, me);
    	me.on('checkchange', me.onCheckChangeHandler, me);
    },
    
    onCheckChangeHandler: function(comp, recordIndex, checked){
    	var me = this,
    		panel = me.up('panel'),
    		store = panel.getStore();
    		
    	Ext.each(store.getRange(), function(record){
    		var eliminated = record.get('eliminated');
    		if(!eliminated){
    			var divEl = me.getHeaderCheckDiv().dom;
    			me.deselectAllHeaderCheck(divEl);
    			return;
    		}
    	});
    },
    
    getHeaderCheckDiv : function(){
    	var me = this;
    	return Ext.get(me.id+'-checkEl');
    },
    
    onHeaderCheckHandler: function(event, el){
    	
    	var me = this,
    		panel = me.up('panel'),
    		store = panel.getStore();
    	
    	panel.getView().setLoading(true);
    	Ext.defer(function(){
    		me.headerCheckChange(el);
	    	Ext.each(store.getRange(), function(record){
	    		if(me.isHeaderCheck){
	    			record.set('eliminated', true, {silent:true});
	    		}else{
	    			record.set('eliminated', false, {silent:true});
	    		}
	    	});
	    	panel.getView().refresh();
	    	panel.getView().setLoading(false);
    	}, 10);
    },
    
    headerCheckChange: function(el){
    
    	var me = this;
    	if(me.isHeaderCheck){
    		me.deselectAllHeaderCheck(el);
    	}else{
    		me.selectAllHeaderCheck(el);
    	}
    },
    
    selectAllHeaderCheck: function(el){
    
    	var me = this;
    	el.style.backgroundPosition = '0 -15px';
		me.isHeaderCheck = true;
    },
    
    deselectAllHeaderCheck: function(el){
    
    	var me = this;
    	el.style.backgroundPosition = '0 0px';
		me.isHeaderCheck = false;
    },
    
    onBeforeCheckChange: function(column, rowIndex, checked) {
    	var me = this,
    		view = column.getView(),
            store = view.getStore();
            
    	me.callParent(arguments);
    	
    	// 삭제 컬럼의 경우, Check 클릭 시 스토어의 Length가 0이면 CheckBox가 남는 현상 조치
    	if(store && store.getRange().length < 1){
        	view.refresh();
    	}
    }
});

/** [TechSupp-1858] Filter 버그 개선 */
Ext.define('Etna.override.grid.plugin.ui.Filter',{
	override : 'Etna.grid.plugin.ui.Filter',
	
	// Fix_9
	onChange : function(newVal, oldVal){
		var me = this;
		
		if (me.rendered && !me.readOnly && !me.disabled && me.editable) {
			me.doQueryTask.delay(me.queryDelay);
		}
		
		me.callParent(arguments);
	},
	
	// Fix_11
	onBlur : function(e){
		var me = this;
		
		if(me.doQueryTask && me.doQueryTask.id){
			me.doRawQuery();
		}
		
		me.callParent(arguments);
	},
	
	
	// Fix_2 and Fix_3
	onFilterTrigger : function() {
    	var me = this,
        grid = me.getGrid(),	
		column = me.getColumn(),
		filter = column.filter,
		triggerFilter;
    	
    	if(me.usingExtFilter === true)
    	{
    		// Fix_2
    		if(!filter.menu) {
				filter.createMenu();
			}
    		
    		// Fix_3
    		grid.headerCt.getMenu().activeHeader = column;
			triggerFilter = filter.menu;
    	}
    	else{
    		triggerFilter = me.filterManager.listFilter;
    	    triggerFilter.setColumn(me.getColumn());
    	    triggerFilter.setOwnerGrid(me.getGrid());
    	    triggerFilter.setOwner(me);
    	}
    	
	    triggerFilter.showBy(me, 'tl-tr?');
	},
	
	unCheckedMenuItems : function(){
		var me = this,
			column = me.getColumn(),
			filter = column.filter;
		
		// Ext Filter를 사용하는게 아닌 경우 별도의 초기화 로직이 필요 없음
		if(!me.usingExtFilter || (filter && !filter.menu)){
			return;
		}
		
		// Ext Filter의 menucheckitem의 check를 해제함 
		Ext.each(filter.menu.query('menucheckitem{checked === true}'),function(menuItems){
			Ext.isFunction(menuItems.setChecked) ?  menuItems.setChecked(false, true) : null;
		});
		
		// Ext Filter의 DatePicker의 값을 초기화
		Ext.each(filter.menu.query('[isDatePicker]'),function(field){
			Ext.isFunction(field.setValue) ?  field.setValue(null) : null;
		});
		
		// Ext Filter의 field의 값을 초기화
		Ext.each(filter.menu.query('[isFormField]'),function(field){
			Ext.isFunction(field.setValue) ?  field.setValue(null) : null;
		});
		
		//Ext Filter를 비활성화(prototype의 setActive의 직접 호출 이유는 setActive 함수를 interCept 하는 Function이 있어 직접호출)
		Ext.ClassManager.getClass(filter).prototype.setActive.call(filter,false);
	},
	
	activate : function() {
		var me = this;
		
		me.unCheckedMenuItems();
		
		me.callParent(arguments);
	},
	
	deactivate : function() {
		var me = this,
			filter = me.getFilter();
		
		filter.setValue(null);
		me.setRawValue(null);
		
		me.callParent(arguments);
	},
	
	deactivateAllFilters : function() {
		var me = this;
		me.setActiveFilter(false);
		me.unCheckedMenuItems();
	},

	// Fix_5
	createFilter : function() {
		var me = this,
			picker = me.getPicker(),
			fm = Etna.grid.plugin.manager.FilterManager,
			column = me.getColumn(),
			filter;
		// Fix_5
		if(column.dataIndex && !(column.xtype === 'etnaeliminatecolumn' || column.xtype === 'etnastatuscolumn')) {
			filter = Ext.create('Ext.util.Filter', {
				operator : null,
				root : 'data',
				property : column.dataIndex,
				value : 'null',
				disabled : true,
				_getColumn : (function(_column) {
					return function() {
						return _column;
					}
				}(column))
			});
			if(fm.contains(column.xtype)) {
				filter.getPropertyValue = fm.getPropertyValueFn(column.xtype)
			}
			me.setFilter(filter);
			me.lastOperator = null;
		}
		else {
			// Fix_5
			me.setDisabled(true);
			if(Ext.isObject(me.triggers) && Ext.isObject(me.triggers.picker) && Ext.isFunction(me.triggers.picker.hide))
				me.triggers.picker.hide();
				Ext.override(me,{
					enableKeyEvents : false,
					createFilterTrigger : Ext.emptyFn,
					activate : Ext.emptyFn,
					deactivate : Ext.emptyFn,
					deactivateAllFilters : Ext.emptyFn,
					setActiveFilter : Ext.emptyFn,
					doRawQuery : Ext.emptyFn,
					setOperator : Ext.emptyFn
				});
		}
	},
        //Fix_6
	setActiveFilter : function(){
		var me = this;
		if(me.rendered === false){
			return;
		}
		me.callParent(arguments);
	},
	
	setupColumnListeners : function() {
		var me = this,
			column = me.getColumn();
		
		me.columnListeners = column.on({
			show : me.onColumnShow,
			hide : me.onColumnHide,
			added : me.onColumnAdded,
			resize : me.onColumnResize,
			// Fix_7
			afterrender : me.onColumnAfterRender,
			destroyable : true,
			scope : me
		});
	},
	
	//Fix_7
	onColumnAfterRender : function(column, e){
		this.setVisible(column.isVisible());
	}
});

/** [TechSupp-1858] Filter 버그 개선 */
Ext.define('Etna.override.grid.plugin.Filter',{
	override : 'Etna.grid.plugin.Filter',
	
	// Fix_4
	filterFieldClsChange : Ext.emptyFn,
		
	deactivate : function(){
		var me = this;
		me.callParent(arguments);
		me.deActivateAllFilters();
	},
	
	deActivateAllFilters : function(){
		Ext.each(this.getAllFilters(),function(filter){
			filter.deactivateAllFilters();
		});
	},
	
	// Fix_1 and Fix_4
	createFilterField : function(grid) {
		var me = this,
			columnManager = grid.getColumnManager(),
			scrollbarSize = Ext.getScrollbarSize(),
			isCheckboxModel = (!grid.view.isNormalView && grid.getSelectionModel() instanceof Ext.selection.CheckboxModel),
			fields = [],
			map = {},
			filterId;
		
		if(isCheckboxModel) {
			fields.push({
				xtype : 'component',
				width : 24,
				cls : 'x-etna-filter-field-checkboxmodel x-form-item-body-default'
			});
		}
		Ext.Array.each(columnManager.getColumns(), function(column) {
			// Fix_1
			if(column.hasOwnProperty('isCheckerHd')){
				return;
			}
			map[column.id] = filterId = Ext.id(null, 'etnafilter-');
			fields.push({
				xtype : 'etnafilter',
				id : filterId,
				column : column,
                filterManager : me,
                // Fix_4
                cls : 'x-etna-filter-field',
				//cls : Ext.String.format('x-etna-filter-field {0} {1}', column.isFirstVisible ? 'isFirst' : '', column.isLastVisible ? 'isLast' : ''),
				grid : grid,
				listeners : {
					filter : me.onFilter,
					activate : me.onActivate,
					deactivate : me.onDeactivate,
					scope : me
				}
			});
		});
		if(!grid.isLocked) {
			fields.push({
				xtype : 'component',
				cls : 'x-etna-filter-field-scrollbar',
				minWidth : scrollbarSize.width,
				flex : 1
			});
		}
		me.setFilterMap(map);
		return fields;
	},
	
	setupStoreListeners : function(store){
		var me = this,
		ownerGrid = me.getCmp(), store = store || ownerGrid.store;
		if(me.storeListeners){
			Ext.destroy(me.storeListeners);
			me.storeListeners = null;
		}
		
		var clearFn = function(){
			this.setActive(false); 
			this.deActivateAllFilters();
		};
		
		Ext.Function.interceptBefore(store, 'removeAll', clearFn, me);
		
		me.storeListeners = store.on({	
			beforeload : clearFn,
			destroyable  : true,
			remove : function(store, records, index, isMove){
				if(store.getCount() === 0){
					this.deActivateAllFilters();
				}
			},
			scope : me
		});
	},
	onBeforeReconfigure : function(grid, store){
		var me = this;
		me.callParent(arguments);
		me.setupStoreListeners(store);
	},
	destroy : function() {
		var me = this;
		
		Ext.destroy(me.storeListeners);
		me.storeListeners = null;
		me.callParent(arguments);
	}
});

Ext.define('Ext.override.resizer.Splitter', {
    override: 'Ext.resizer.Splitter',
    renderTpl: [
        '<tpl if="collapsible===true">',
            '<div id="{id}-collapseEl" data-ref="collapseEl" role="presentation" class="', Ext.baseCSSPrefix, 'collapse-el ',
                Ext.baseCSSPrefix, 'layout-split-{collapseDir}{childElCls}">&#160;',
            '</div>',
        '</tpl>',
        '<tpl if="collapsible!==true">',
            '<div class="',Ext.baseCSSPrefix, 'split-{collapseDir}-markerFirst"></div>',
            '<div class="',Ext.baseCSSPrefix, 'split-{collapseDir}-markerSecond"></div>',
        '</tpl>'
    ]
});


/** [TechSupp-1986] IE에서 기능 멈추는 이상현상 간헐적 발생 */
window.onTouchEndExceptionCount = 0; // 임시테스트용
window.onTouchEndException = [];
Ext.define('Etna.override.event.publisher.Gesture', {
	override: 'Ext.event.publisher.Gesture',
	onTouchEnd: function(e) {
        var me = this;

        if (!me.isStarted) {
            return;
        }

		me.updateTouches(e, true);
		try{
	        me.invokeRecognizers(me.isCancelEvent[e.type] ? 'onTouchCancel' : 'onTouchEnd', e);
		} catch(e){
			// Exception 발생 원인 출력 
			Ext.log.warn('[Ext.event.publisher.Gesture] onTouchEnd Exception: '+e.stack);
			window.onTouchEndException[window.onTouchEndExceptionCount++] = e;
		} finally{
			if (!me.activeTouches.length) {
            
	            me.isStarted = false;
	            me.invokeRecognizers('onEnd', e);
	
	            if (Ext.enableGarbageCollector) {
	                Ext.dom.GarbageCollector.resume();
	            }
	        }
		}
    }
});

/** [TechSupp-1813] */ 
Ext.define('Cmmn.override.upload.StoreBasedUploader', {
	override: 'Etna.upload.StoreBasedUploader',
	initComponent: function(){
		var me = this;
		
		me.setReference(me.getReference()+'_storebaseduploader');
		me.callParent(arguments);
	}
});


Ext.define('Mdi.override.ux.TabCloseMenu', {
    override : 'Mdi.ux.TabCloseMenu',
    
    closeTabText: '#{탭 닫기}',
    closeOthersTabsText: '#{다른 탭 닫기}',
    closeAllTabsText: '#{모든 탭 닫기}',
    
});



// 2016-07-29 kjw
// TECHSUPP-1592 Ext Direct 버퍼링 조정 적용.
//Ext.define('Site.direct.RemotingProvider', {
//	override : 'Ext.direct.RemotingProvider',
//	bufferLimit : 5, //Ext Direct 최대 버퍼의 개수를 5로 제한
//    queueTransaction : function(transaction) {
//    	var me = this,
//    	    callBuffer = me.callBuffer,
//    	    enableBuffer = me.enableBuffer;
//    	
//    	if(transaction.form) {
//    		me.sendFormRequest(transaction);
//    		return;
//    	}
//    	
//    	if(enableBuffer === false || transaction.disableBatching || typeof transaction.timeout !== 'undefined') {
//    		me.sendRequest(transaction);
//    		return;
//    	}
//    	
//    	callBuffer.push(transaction);
//    	
//    	if(enableBuffer && callBuffer.lenght < me.buggerLimit) {
//    		if(!me.callTask) {
//    			me.callTask = new Ext.util.DelayedTask(me.combineAndSend, me);
//    		}
//    		
//    		me.callTask.delay(Ext.isNumber(enableBuffer) ? enableBuffer : 10);
//    	}
//    	else {
//    		me.combineAndSend();
//    	}
//    	
//    }
//});


Ext.define('Etna.override.toolbar.ScrollPaging', {
    override: 'Etna.toolbar.ScrollPaging',
	onScroll: Ext.Function.createBuffered(function(view) {
	    var me = this,
	        grid = me.getGrid(),
	        dataSource = view.dataSource,
	        bufferedRenderer = view.bufferedRenderer,
	        count = dataSource.getCount();
	    if (me.keydown || !count) {
	        return;
	    }
	    if (bufferedRenderer && (dataSource.getTotalCount() - me.duplicatedCount) > count) {
	        if (view.all.endIndex + 1 == dataSource.getCount() && view.all.last().getBottom() <= (view.el.getBottom()+2)) {
	            me.loadNextPage();
	        }
	    }
	}, 100)
});


/**
 * TECHSUPP-2007
 * 그리드 컬럼 내 2개 값 선택가능하도록 
 * 시작
 */
Ext.define('Etna.grid.column.Column', {
    override: 'Ext.grid.column.Column',
    initComponent: function(){
    	var me = this;
    	if(me.textItems){
    		me.renderer = me.textItemRenderer;
    	}
    	me.callParent(arguments);
    },
    textItemRenderer: function(value, metaData, record, rowIndex, colIndex, store, view){
    	var me = (this.isColumn) ? this: metaData.column,
    		panel = me.up(me.ctAlias),
    		controller = panel.controller,
    		validation = me.textItemsValidation,
    		editable, id = Ext.id();
	
    	if(controller && validation){
    		editable = controller[validation].call(panel, panel, record); // scope, arg1, arg2
    	}
    	
		Ext.defer(function(){
			Ext.create('Ext.container.Container', {
				width: 100,
				layout : {
					type: 'hbox',
					align : 'stretch',
					pack : 'center'
				},
				defaults: {
					padding: '0px 0px 1px 0px'
				},
				style: {
					display: 'inline-block'
				},
				editableCls : Ext.baseCSSPrefix + 'renderer-label-enabled',
    			selectedCls : Ext.baseCSSPrefix + 'renderer-label-selected',
				renderTo : Ext.query('#'+id)[0],
				column: me,
				items : me.textItems,
				record : record,
				listeners: {
					afterrender: function(cmp, eOpts){
						var me = this;
							labels = me.query('label');
							
						Ext.each(labels, function(label){
						
							if(Ext.isEmpty(label.editable)){
								label.editable = true;
							}
							
							if(editable || (!validation && label.editable)){
								label.addCls(me.editableCls);
							}
							if(value === label.valueField ){
								me.fireEvent('selectedItem', label);
							}
							
							/** Click Event 등록 */
							label.el.on('click', function(){
								if(editable || (!validation && label.editable)){
									me.fireEvent('selectedItem', label);
								}
							});
						});
					},
					selectedItem: function(_label){
						var me = this,
							record = me.record,
							dataIndex = me.column.dataIndex,
							labels = me.query('label');
						
						Ext.each(labels, function(label){
							if(_label.valueField === label.valueField){
								label.addCls(me.selectedCls);
								label.removeCls(me.editableCls);
							}else{
								label.removeCls(me.selectedCls);
								if(editable || (!validation && label.editable)){
									label.addCls(me.editableCls);
								}
							}
						});
						
						record.set(dataIndex, _label.valueField);
					}
				}
			});
		}, 1);
		
		return Ext.String.format('<div id="{0}" style="width:100%;height:15px;"></div>', id);
    }
});
/**
 * TECHSUPP-2007
 * 그리드 컬럼 내 2개 값 선택가능하도록 
 * 끝
 */

/** [2016.08.18] 권한이 없는 포틀릿에 접근시 발생하는 오류 조치 */
Ext.define('Etna.override.dashboard.Dashboard', {
    override: 'Ext.dashboard.Dashboard',
    createView: function (config) {
        var me = this,
            type = config.type,
            part = me.getPart(type);

        if(Ext.isEmpty(part)){
        	return null;
        }

        return me.callParent(arguments);
    }
});

/** [2016.08.24] 간헐적으로 개인화 기능 안되는 현상 조치 */
Ext.define('Mdi.override.controller.Manager', {
    override: 'Mdi.controller.Manager',
    addView : function(className, config, requireClasses, callback){
    	var me = this;
    	Etna.security.Manager.setAuthKey(config.authKey);
    	me.callParent(arguments);
    },
    showSpMain : function(){
    	var loadUrl = 'main/splogin.jsp';
    	var topSize = 120; //2024.03.06 scyang 75 to 120
    	var heightSize = 'calc(100% - 120px)'; //2024.03.06 scyang 75 to 120
    	if(isForeign){
    		loadUrl = 'main/frlogin.jsp';
    		topSize = 0; 
    		heightSize = '100%';
    	}
    	var me = this;
    	if(!me.spmain){
    		if(me.mdiTab){
    			me.mdiTab.hide();
    		}
    		var onMouseDown = Ext.Function.createInterceptor(Ext.Function.bind(Ext.menu.Manager.onMouseDown, Ext.menu.Manager), function(){
    			return Ext.menu.Manager.attached;
    		});
    		Ext.getWin().on('resize', me.resizeHandler, me);
    		me.spmain = Ext.create('Mdi.ux.IFrame', {
    			src : loadUrl,
    			x : 0,
    			y : topSize,
    			cls : 'spmain',
    			style : {
    				width : '100%',
    				height : heightSize
    			},
    			floating : true,
    			closeAction : 'destroy',
    			shadow : false,
    			autoShow : true,
    			listeners : {
    				render : function (cmp){
    					cmp.iframeEl.dom.contentWindow.addEventListener('mousedown', onMouseDown);
    					//cmp.load('main/splogin.jsp');
    				},
    				destroy : function(){
    					this.iframeEl.dom.contentWindow.removeEventListener('mousedown', onMouseDown);
    				}
    			}
    		});
    	}
    	 //김형민 부적절한 페이지 제목제공 pdf#40
    	Ext.query('title')[0].innerHTML = '한국전력 전자조달 시스템';
    	if(me.mdiTab) {
    		var viewPort = me.mdiTab.up();
//    		viewPort.lookupReference('tools').hide();
    		viewPort.lookupReference('mdiTabPanel').hide();
    		viewPort.down('mdileft').hide();
    		viewPort.down('mditop').items.items[2].hide();
    	}
    },
    setCurrentLocale: function(locale) {   //새로 추가하기
   	 localStorage.removeItem(Ext.String.format('i18n-{0}.lastUpdated', Etna.i18n.Manager.getLocale()));
            return this.callParent(arguments);
    }
});

/**포탈에서 메뉴 클릭시 간헐적으로 b.sort에러 조치*/
window.toolsArrCount = 0;
window.toolsArrException = [];
Ext.define('Portal.override.controller.PartFactory', {
	override : 'Portal.controller.PartFactory',
	getTools : function(portlet) {
		var me = this,
			toolsArr = portlet.get('tools');
		
		try{ 
			return me.callParent(arguments);
		} catch(e) {
			window.toolsArrException[window.toolsArrCount++] = e;
			Ext.Logger.warn("[Exception]" + e);
			return [];
		}
	}
});

/** [2016.09.01] 조회요청 중 스페셜 키(엔터를 이용한 검색) 이벤트를 막는 조치 */
Ext.define('Site.override.form.field.Base', {
	override : 'Ext.form.field.Text',
	
    fireKey: function(e){
    	var me = this;
        if(e.isSpecialKey()){
        	if(me.isMasked(me)){
        		return;
        	}
            this.fireEvent('specialkey', this, e);
        }
    },
});

/**
 * [2016.09.09] 제작규격용 첨부파일 컴포넌트
 */
Ext.define('Site.extends.upload.ui.FloorplanColumnGrid',{
	extend: 'Etna.upload.ui.Grid',
	alias: 'widget.floorplancolumngrid',
	
    updateActionColumnLabel : '#{변경}',
    
    createColumns: function() {
    	var me = this, columns = me.callParent(arguments);
    	
    	columns.splice(2, 0, {
    		text: me.updateActionColumnLabel,
    		width : 80,
    		xtype:'actioncolumn',
    		iconCls: 'icon-touch',
    		align: 'center',
    		handler : function(grid, rowIndex, colIndex, item, e, record, row){
    			var status = record.get('status'),
					originalId = record.get('originalId');
                if(status == 5 || status == 6 || originalId){
                	var browseBtn = me.uploader.getBrowseButton();
                	if(me.uploader.readOnly === false && browseBtn && !browseBtn.isDisabled()){
                		browseBtn.suspendEvents();
                		browseBtn.getEl().dom.click();
                		browseBtn.resumeEvents();
                    	me.uploader.currentEditingRecord = record;
                	}
                }
    		},
    		isDisabled: function(view, rowIndex, colIndex, item, record) {
    			var status = record.get('status'),
					originalId = record.get('originalId');
                if(status == 5 || status == 6 || originalId){
                    return false;
                }else{
                    return true;
                }
            }
    	});
    	return columns;
    },
    statusColumnRenderer: function(value, meta, record, rowIndex, colIndex, store, view) {
        var status = record.get('status'),
        	originalId = record.get('originalId'),
            statusClass;
        if(status === 6 || originalId){
        	statusClass = "update";
        }else if(status === 5){
        	statusClass = "remote";
        }else if(status === 1 || status === 2){
        	statusClass = "local";
        }
        return '<div class="x-etna-grid-uploader-status-' + statusClass + '">';
    }
});

Ext.define('Site.extends.upload.FloorplanStoreBaseUploader',{
	extend : 'Etna.upload.StoreBasedUploader',
	requires : ['Site.extends.upload.ui.FloorplanColumnGrid'],
	uiClasses : ['Site.extends.upload.ui.FloorplanColumnGrid'],
	listUrl : 'smartsuit.ui.etnajs.sim.floorplanmgt.DrawingFileAttachmentController.getDrawingFileListOnUpdate',
	deleteUrl : 'smartsuit.ui.etnajs.sim.floorplanmgt.DrawingFileAttachmentController.removeAttachmentOnUpdate',
	
	onPluploadBeforeUpload: function(uploader, file) {
		var me = this;
		var requestType = me.up('[controller]').getViewModel().get('basicInfo.requestType'); 
        var param = uploader.settings.multipart_params;
        param.requestType = requestType;
        
        
        if(file.updateId){
        	param.updateId = file.originalId; 
        }else{
        	delete param.updateId;
        }
        
        return me.callParent(arguments);
    },
    
	onPluploadFilesAdded: function(uploader, files) {
        var me = this;
        if (me.readOnly || me.enforceReadOnly) {
            return false;
        }
        if(this.currentEditingRecord && files.length === 1){
        	files[0].updateId = this.currentEditingRecord.id;
        	if(this.currentEditingRecord.get('originalId')){
        		files[0].originalId = this.currentEditingRecord.get('originalId');
        	}else{
        		files[0].originalId = this.currentEditingRecord.id;
        	}
        }
        return me.callParent(arguments);
    },
    
    updateFile: function(file) {
        var me = this,
            store = me.getStore(),
            record = store.getById(file.updateId),
            re = /(?:\.([^.]+))?$/;
        
        file.extension = re.exec(file.name).pop();
        if (record) {
            record.set(file);
            record.commit();
        } else {
            record = store.add(file)[0];
        }
        
        if(file.updateId){
        	var uploader = me.getUploader();
        	uploader.removeFile(file.updateId);
        }
    },
	
	afterRender : function(){
		var btn = this.getBrowseButton();
		this.btnListeners = btn.on({
			destroyable: true,
			click: function(){
				this.currentEditingRecord = null;
			},
			scope : this
		});
		
		return this.callParent(arguments);
	},
    
    onDrop: function(e) {
    	if(e){
    		this.currentEditingRecord = null;
    	}
    	return this.callParent(arguments);
    },
	
    destroy : function(){
    	Ext.destroy(this.btnListeners);
    	return this.callParent(arguments);
    }
});

Ext.define('Site.extends.form.field.FloorplanAttachment',{
	extend : 'Etna.form.field.Attachment',
	alias : 'widget.floorplanAttachmentfield',
	requires : ['Site.extends.upload.FloorplanStoreBaseUploader'],
	uploaderClass : 'Site.extends.upload.FloorplanStoreBaseUploader'
});


/** [2016.10.05] EMailDetailViewController.js, WebMessageDetailViewController.js에서 사용 */
Ext.define('Site.util.ATag', {
	
	/** 1. A태그 클릭 시, MDI탭에 추가 되기 위한 로직 */
    replaceForAddView: function(changeContent){
    	
    	var me = this, result = {},
    		copiedContent = changeContent;
    	
    	// A태그 배열 생성
    	var aTagItems = me.parseFromContentToATag(copiedContent);
    	
    	// A태그 배열 For문
    	Ext.each(aTagItems, function(item){
    		var modifiedItem = item;
    		
    		modifiedItem = me.modifyAHref(modifiedItem); // href 생성
    		modifiedItem = me.modifyATarget(modifiedItem); // target 생성
    		
    		result[item] = modifiedItem; // 맵 생성 ( key : 기존 값, value : 수정 값 )
    	});
    	
    	for(var key in result){
    		changeContent = changeContent.replace(key, result[key]);
    	}
    	
    	return changeContent;
    },
    
    /** A태그 스트링 배열을 리턴 */
    parseFromContentToATag: function(_copiedContent){
    	var aTagItems = [], splitContents = [], aTag,
    		regex = /<a.*?href=.*?<\/a>/; // A Tag
    	
    	while(regex.test(_copiedContent)){
    		aTag = regex.exec(_copiedContent)[0];
    		
    		if( aTag.indexOf("<a href=") > -1
    			&& aTag.indexOf("srm.kepco.net") > -1  
    			&& aTag.indexOf("classpath") > -1){
    			
    			/** 변경 대상 A태그 체크 */
    			aTagItems.push(aTag);
    		}
    		splitContents = _copiedContent.split(aTag);
    		_copiedContent = splitContents[1];
    	}
    	
    	return aTagItems;
    },
    
    /** A태그 href 수정 */
    modifyAHref: function(_aTag){
    	var regex = /<a.*?href="(.*?)"/;
        var ahref = regex.exec(_aTag);
        if(ahref){
            var hrefStr = ahref[1], //href안의 문자 추출
            	classpathArr	=	hrefStr.split("classpath="),
            	deClasspath		=	classpathArr[1];

            _aTag = _aTag.replace(hrefStr,"javascript:addMdiTab('"+deClasspath+"')");
        }
        
    	return _aTag;
    },
    
    /** A태그 target 수정 */
    modifyATarget: function(_aTag){
    	var regex = /<a.*?target="(.*?)"/;
        var atarget = regex.exec(_aTag);
        if(atarget){
            var aStr = atarget[1]; //href안의 문자 추출
            _aTag = _aTag.replace(aStr,"_self");
        }
        
    	return _aTag;
    }
});

/** [2016.10.05] 다수의 첨부파일 업로드 시, 업로드가 되지 않는 현상 조치 */
Ext.define('Etna.override.upload.ui.Grid', {
    override: 'Etna.upload.ui.Grid',
    
    beforeUpload: function(file) {
        var me = this,
        	view = me.view,
            record = me.store.getById(file.id),
            row = view.getRowByRecord(record);
        
        if(row){
        	me.callParent(arguments);
        }
    },
    
    updateProgress: function(percent, file) {
        var me = this,
            record = me.store.getById(file.id),
            row = me.view.getRowByRecord(record);
        
        if(row){
        	me.callParent(arguments);
        }
    },
    
    fileUploaded: function(file) {
        var me = this,
            record = me.store.getById(file.id),
            row = me.view.getRowByRecord(record);
        
        if(row){
        	me.callParent(arguments);
        }
    }
});

/** [ Number값 강제 String 변환 ] KEP-17
  * 1. (전체 적용) ExportManager / numToStringColumn:true 
  * 2. (컬럼 적용) NumberColumn / forceString:true 
  */
Ext.define('Etna.grid.plugin.manager.ExportManager', {
	override: 'Etna.grid.plugin.manager.ExportManager',
	numToStringColumn: true,
    getMetaData: function(column, forceString) {
        var me = this, metaData;
        metaData = me.callParent(arguments);
	    
	    if( me.isPossibleNumToString(column) ){
        	metaData['format'] = '';
        	metaData['type'] = me.DATA_TYPE.STRING;
        }
        
        return metaData;
    },
    
    getValue: function(column, record, force) {
        var me = this, value;
        value = me.callParent(arguments);
        
        if (!Ext.isEmpty(value, true)) {
    		return me.getNumberFormatValue(column, value);
        }
        return '';
    },
    
    getNumberFormatValue: function(column, value){
    	var me = this;
    	if(me.isPossibleNumToString(column)){
    		return Ext.util.Format.number(value, column.format).toString();
    	}
		return value;
    },
    
    /** Number Column에 한해서 number값을 string값으로 변환 가능여부 */
    isPossibleNumToString: function(column){
    	var me = this, config = column.config,
    		renderer = config.renderer;
    	
    	if( (me.numToStringColumn||column.forceString) ){
    		if(column.xtype && column.xtype === 'numbercolumn'){
    			/** 컬럼에 커스텀 렌더러 존재하는 경우, false 리턴 */
	    		return (renderer) ? false : true;
    		}
    	}
		return false;
    }
});

/** (IE에서만 발생) 공지사항 첨부파일 안뜨는 현상 */
Ext.data.Connection.prototype.setOptions = function(options, scope) {
    var me = this,
        params = options.params || {},
        extraParams = me.getExtraParams(),
        urlParams = options.urlParams,
        url = options.url || me.getUrl(),
        jsonData = options.jsonData,
        method,
        disableCache,
        data;

	/**
	 * [현상] IE에서 새창을 띄워, opener.Ext.Ajax.request를 통해 호출하는 경우
	 *       넘어오는 'param'를 아래의 Ext.isFunction에 체크를 하면
	 *       Function이 아님에도 불구하고 true값을 리턴. params.call()을 호출하여 에러 발생.
	 * [조치] 그래서 아래와 같이 params.call 존재여부 확인 후 호출하도록 수정함.
	 */
    if (Ext.isFunction(params)) {
		if(params.call){
			params = params.call(scope, options);
		}
    }
    
    if (Ext.isFunction(url)) {
        url = url.call(scope, options);
    }

    url = this.setupUrl(options, url);

    if (!url) {
        Ext.Error.raise({
            options: options,
            msg: 'No URL specified'
        });
    }
    
    data = options.rawData || options.binaryData || options.xmlData || jsonData || null;
    if (jsonData && !Ext.isPrimitive(jsonData)) {
        data = Ext.encode(data);
    }
    
    if (options.binaryData) {
        if (!Ext.isArray(options.binaryData)) {
            Ext.log.warn("Binary submission data must be an array of byte values! Instead got " + typeof(options.binaryData));
        }
        if (me.nativeBinaryPostSupport()) {
            data = (new Uint8Array(options.binaryData));
            if ((Ext.isChrome && Ext.chromeVersion < 22) || Ext.isSafari || Ext.isGecko) {
                data = data.buffer; 
            }
        }
    }

    if (Ext.isObject(params)) {
        params = Ext.Object.toQueryString(params);
    }

    if (Ext.isObject(extraParams)) {
        extraParams = Ext.Object.toQueryString(extraParams);
    }

    params = params + ((extraParams) ? ((params) ? '&' : '') + extraParams : '');

    urlParams = Ext.isObject(urlParams) ? Ext.Object.toQueryString(urlParams) : urlParams;

    params = this.setupParams(options, params);

    
    method = (options.method || me.getMethod() || ((params || data) ? 'POST' : 'GET')).toUpperCase();
    this.setupMethod(options, method);


    disableCache = options.disableCaching !== false ? (options.disableCaching || me.getDisableCaching()) : false;
    
    if (method === 'GET' && disableCache) {
        url = Ext.urlAppend(url, (options.disableCachingParam || me.getDisableCachingParam()) + '=' + (new Date().getTime()));
    }

    if ((method == 'GET' || data) && params) {
        url = Ext.urlAppend(url, params);
        params = null;
    }

    if (urlParams) {
        url = Ext.urlAppend(url, urlParams);
    }

    return {
        url: url,
        method: method,
        data: data || params || null
    };
}

/** 파일 조회 시, ID의 암호화를 하고 싶지 않은 경우 'noneEnc'속성 사용 */
/**Ext.define('Etna.override.upload.StoreBasedUploader', {
	override : 'Etna.upload.StoreBasedUploader',
	beforeSetValue: function(value, binding) {
		var me = this, params,
		    isEmptyValue = Ext.isEmpty(value);
		    
		if (!binding && me.value != value) {
		    if (isEmptyValue && me.getStore().getCount() > 0) {
				me.beforeReset();
		    } else if (me.autoLoad && !isEmptyValue) {
		    	params = {groupId:value};
		    	if(me.noneEnc){
		    		params.noneEnc = true;
		    	}
				me.load({
				    params: params
				});
		    }
		}
		return me;
	}
});*/

//2019.05.27 에너지밸리 썸네일
Ext.define('Override.Etna.upload.Uploader',{
	override : 'Etna.upload.Uploader',
	
	initPlUpload: function(initializer) {
        var me = this,
            initializer = initializer || function(fn, scope) {
                fn.call(scope);
                Ext.Logger.log(me.id + ' plupload init function called');
            },
            dropEl;
	    if(me.useDragDrop){
	        dropEl = me.getDropElementId();
	    }
        var uploader = new plupload.Uploader({
                uploader: me,
                url: me.uploadUrl,
                headers: me.getMultipartHeaders(),
                filters: me.getPluploadFilter(),
                runtimes: me.pluploadRuntimes,
                flash_swf_url: me.flashSwfUrl,
                silverlight_xap_url: me.silverlightXapUrl,
                browse_button: me.getBrowseButtonId(),
                drop_element: dropEl,
                multi_selection: me.getMultiSelection(),
                multipart: true
            });
        delete me.initialized;
        Ext.Array.each([
            'Init',
            'PostInit',
            'FilesAdded',
            'QueueChanged',
            'FilesRemoved',
            'FileUploaded',
            'BeforeUpload',
            'StateChanged',
            'UploadProgress',
            'Error',
            'Destroy'
        ], function(v) {
            uploader.bind(v, Ext.Function.alias(me, 'onPlupload' + v), me);
        }, me);
        me.setUploader(uploader);
        initializer(uploader.init, uploader);
    }
});


Ext.define('Etna.form.field.SingleThumbnailAttachment', {
  extend: 'Ext.form.FieldContainer',
  alias: 'widget.singlethumbnailattachment',
  cls: 'single-thumbnail-attachment',
  config: {
      /**
		 * @cfg {Etna.upload.Uploader} uploader 
		 * @accessor
		 * 첨부파일 컴포넌트
		 */
      uploader: null
  },
  /**
	 * @cfg {Ext.enums.Layout/Object} layout
	 * 첨부파일 필드 레이아웃
	 */
  layout: 'fit',
  /**
	 * @cfg {Boolean} readOnly
	 * 첨부파일 버튼 활성화 여부
	 */
  readOnly: false,
  /**
	 * @cfg {Array} eliminateUploaderCfgs
	 * 업로더 생성시 제외되는 config 명
	 */
  eliminateUploaderCfgs: [
      'margin',
      'padding',
      'plugins'
  ],
  /**
	 * @property {Ext.minins.Bindable} bind 사용시 바인딩할 프로퍼티 명
	 * @private
	 */
  defaultBindProperty: 'value',
  /**
	 * @property {Etna.upload.Uploader} 파일첨부 컴포넌트 클래스 
	 * @private
	 */
  uploaderClass: 'Etna.upload.StoreBasedThumbnailUploader',
  /**
	 * @constructor
	 * @param {Object} config 설정
	 */
  constructor: function(config) {
      var me = this;
      if (!config.name) {
          Ext.apply(config, {
              name: 'singleattachmentfield-' + Ext.id()
          });
      }
      me.callParent(arguments);
  },
  /**
	 * @private
	 * 컴포넌트 초기화<p>
	 * {@link Etna.upload.Uploader} 를 FieldContainer 의 items 로 지정하고 Uploader 의 메소드를 바인딩 함
	 */
  initComponent: function() {
      var me = this;
      me.createUploader(me.getUploaderConfig());
      Ext.apply(me, {
          items: me.getUploader()
      });
      me.bindFieldMethod();
      me.callParent(arguments);
  },
  /**
	 * @private
	 */
  afterRender: function() {
      var me = this,
          uploader = me.getUploader();
      me.callParent(arguments);
      if (Ext.isIE9m && me.ownerLayout.type == 'table') {
          Ext.Function.interceptAfter(me.ownerLayout, 'moveItem', function(item) {
              if (item.id == me.id) {
                  Ext.Logger.log(uploader.id + ' moveitem');
                  uploader.reinitPlUpload();
              }
          });
      }
  },
  /**
	 * @private
	 * 업로더 객체 생성시 필요한 config
	 */
  getUploaderConfig: function(config) {
      var me = this,
          initialConfig = me.getInitialConfig(),
          config = {};
      for (var prop in initialConfig) {
          //http://alm.emro.co.kr/browse/TECHSUPP-1953 reference속성이 넘어가지 않도록 수정
          if (Ext.Array.contains(me.eliminateUploaderCfgs, prop) || Ext.isEmpty(initialConfig[prop], true) || prop == 'reference') {
              
              continue;
          }
          config[prop] = initialConfig[prop];
      }
      return config;
  },
  /**
	 * @private
	 * 등록한 이벤트를 제거한다.
	 */
  destroy: function() {
      var me = this,
          uploader = me.getUploader();
      Ext.destroy(me.uploaderListeners);
      uploader.destroy();
      me.uploader = null;
      me.callParent(arguments);
  },
  /**
	 * @private
	 * {@link Etna.upload.Uploader} 의 메소드를 {Etna.form.field.Attachment} 인스턴스로 바인딩 함
	 */
  bindFieldMethod: function() {
      var me = this,
          uploader = me.getUploader();
      Ext.Array.each([
          'getValue',
          'setValue',
          'load',
          'reset',
          'upload',
          'download',
          'hasUploadFiles',
          'getTransmitFiles',
          'getDeleteFiles',
          'getAttachedFiles',
          'hasAttachedFiles',
          'hasAttachedFileCount',
          'selectFiles',
          'selectAllFiles',
          'deselectFiles',
          'deselectAllFiles',
          'setHideDeleteButton',
          'setHideUploadButton'
      ], function(v) {
          me[v] = Ext.Function.bind(uploader[v], uploader);
      });
  },
  /**
	 * @method createUploader
	 * @param {Object} config 설정
	 * {@link Etna.upload.Uploader} 를 생성하고 이벤트를 등록 및 릴레이 함
	 */
  createUploader: function(config) {
      var me = this,
          uploader;
      uploader = Ext.create(me.uploaderClass, Ext.applyIf(Ext.clone(config), {
      }));
      me.uploaderListeners = uploader.on({
          destroyable: true,
          uploadfailed: me.showErrorMsg
      });
      me.setUploader(uploader);
  },
  /**
	 * @method hasUploadFiles
	 * @protected
	 * 파일첨부 및 업로드 발생한 에러메세지를 보여줌
	 */
  showErrorMsg: function(failed) {
      var me = this,
          msg, title;
      switch (failed[0].code) {
          case -600:
          case -601:
          case -602:
          case -603:
              title = '파일첨부';
              break;
          default:
              title = '파일업로드';
              break;
      }
      msg = Ext.String.format('<div style="line-height:26px;font-weight:bold;">{0} 오류가 발생되었습니다.</div><table>', title);
      Ext.Array.each(failed, function(data) {
          if (data.file) {
              msg += Ext.String.format('<tr><td>{0} :</td><td><span style="color:red">{1}</span></td></tr>', data.file.name, data.response || data.message);
          } else {
              msg += Ext.String.format('<tr><td><span style="color:red">{0}</span></td></tr>', data.response || data.message);
          }
      });
      msg += '</table>';
      Ext.Msg.alert({
          title: title,
          message: msg,
          buttons: Ext.MessageBox.OK,
          icon: Ext.MessageBox.ERROR
      });
      return false;
  },
  /**
	 * @method setAutoLoad
	 * @param {Boolean} value 자동조회속성
	 * */
  setAutoLoad: function(value) {
      var me = this,
          uploader = me.getUploader();
      uploader.setAutoLoad(value);
  },
  /**
	 * @method setReadOnly
	 * @param {Boolean} value 읽기속성
	 * */
  setReadOnly: function(value) {
      var me = this,
          uploader = me.getUploader();
      if (me.readOnly != value) {
          me.readOnly = value;
          uploader.setReadOnly(value);
      }
  },
  /**
	 * @protected afterComponentLayout
	 * */
  afterComponentLayout: function(width, height, oldWidth, oldHeight) {
      var me = this,
          panel = me.up('panel'),
          uploader, bodyWidth;
      if (me.rendered && panel && panel.layout.type == 'table') {
          uploader = me.getUploader();
          //http://alm.emro.co.kr/browse/TECHSUPP-313
          if (me.rendered && uploader.getWidth() != (bodyWidth = me.bodyEl.getWidth())) {
              uploader.suspendLayouts();
              uploader.setWidth(bodyWidth);
              uploader.resumeLayouts({
                  isRoot: true
              });
          }
      }
      me.callParent(arguments);
  }
});

Ext.define('Etna.upload.ui.ThumbnailView', {
  extend: 'Ext.view.View',
  alias: 'widget.etnathumbnailviewuploader',
  mixins: {
      storeBasedView: 'Etna.upload.ui.StoreBasedView'
  },
  config: {
      /**
		 * @cfg {Etna.upload.StoreBasedThumbnailUploader} uploader
		 * @accessor
		 * uploader 객체
		 */
      uploader: null
  },
  /**
	 * @cfg {Boolean} autoScroll
	 */
  autoScroll: true,
  /**
	 * @cfg {String} cls
	 */
  cls: Ext.baseCSSPrefix + 'etna-dataview-single-uploader',
  /**
	 * @cfg {String} overItemCls
	 */
  overItemCls: Ext.baseCSSPrefix + 'etna-dataview-single-item-over',
  /**
	 * @cfg {String} itemSelector
	 */
  itemSelector: 'div.x-etna-dataview-single-item',
  /**
	 * @cfg {Ext.selection.Model/Object} selModel
	 */
  selModel: {
      mode: 'SIMPLE',
      locked: true,
      deselectOnContainerClick: false
  },
  /**
	 * @cfg {Array} 첨부파일 업로드 프로그래스바 색상
	 */
  progressGradientColors: [
      '#EEE',
      '#539FDC'
  ],
  /**
	 * @cfg {Boolean} thumbnail
	 * 썸네일 이미지 활성화 여부
	 */
  thumbnail: true,
  /**
	 * @cfg {String} type
	 * up class type
	 */
  type: 'dataview',
  /**
	 * @cfg {String} dataViewButtonIconCls dataview 버튼 스타일 
	 */
  toggleButtonIconCls: Ext.baseCSSPrefix + 'etna-uploader-dataview-icon',
  /**
	 * @cfg {Ext.XTemplate/Ext.Template/String/String[]} tpl
	 */
  tpl: [
  	'<tpl for=".">',
  	   '<div class="x-etna-dataview-single-item">',
	       	   '<div dataview-item-id="{id}" class="single-file-wrap">',
	       	   	   '<tpl if="this.isIE8()">',
	       	   	   		'<div class="ie8-wrap">',
	       	   	   '</tpl>',
		           '<tpl if="this.isImage(values)">',
		           		'<div class="singleThumb">',
			           		'<tpl if="!this.isReadOnly(values)">',
		           				'<div class="status {[this.statusIconCls(values)]}"></div>',
		           			'</tpl>',
		           			'<tpl if="downloadUrl != null && thumbnailUrl != null">',
		           			'<a class="shadowbox" rel="shadowbox;player=img" href="{downloadUrl}">',
		           				'<img src="{thumbnailUrl}"></img>',
		           			'</a>',	
		           			'</tpl>',
	           			'</div>',
		           '<tpl else>',
		           		'<div class="other">',
      				'</div>',
		           '</tpl>',
		           '<tpl if="this.isIE8()">',
	      	   	   		'</div>',
	      	   	   '</tpl>',
	           '</div>',
	       '</div>',
	   '</tpl>',
      {
          isImage: function(values) {
              return !!values.thumbnailUrl;
          },
          statusIconCls: function(values) {
              var cls = [
                      'default'
                  ];
              if (values.status == 1) {
                  cls.push('local');
              } else if (values.status == 6) {
                  cls.push('update');
              }
              if (this.scope.getSelectionModel().isSelected(values)) {
                  cls.push('delete');
              }
              return cls.join(' ');
          },
          statusDownloadCls: function(values) {
              if (values.status == 5) {
                  return 'download';
              }
              return;
          },
          isReadOnly: function(values) {
              var scope = this.scope;
              if (scope.getUploader().hideDownloadButton) {
                  return scope.readOnly;
              }
          },
          isIE8: function() {
              return Ext.isIE8m;
          }
      }
  ],
  /**
 * @constructor
 * @param {Object} config
 */
  constructor: function(config) {
      var me = this;
      //5.1 에서 에러 발생
      //me.initConfig(config);
      me.callParent(arguments);
      me.initShadowbox();
      me.setupViewListeners();
      me.setupSelectionModelListeners();
  },
  thumnailUrl: null,
  thumnailDownloadUrl: null,
  /**
	 * @private
	 * dataview 컴포넌트 초기화
	 */
  initComponent: function() {
      var me = this,
          tpl = new Ext.XTemplate(me.tpl),
          sm = me.getSelectionModel();
      me.tpl = Ext.apply(tpl, {
          scope: me
      });
      Ext.apply(me, {
          prepareData: function(data) {
          	var elWidth = this.getWidth(),
          		elHeight = this.getHeight();
              if (data.status == 5 && data.mimeType && data.mimeType.indexOf('image') > -1) {
                  if (me.thumnailUrl) {
                      data['thumbnailUrl'] = me.thumnailUrl + '?' + Ext.Object.toQueryString({
                          id: data.id,
                          width: elWidth,
                          height: elHeight
                      });
                  }
                  if (me.thumnailDownloadUrl) {
                      data['downloadUrl'] = me.thumnailDownloadUrl + '?id=' + data.id;
                  }
              }
              return data;
          }
      });
      Ext.Array.each([
          {
              object: me,
              methods: [
                  'select',
                  'selectAll',
                  'deselect',
                  'deselectAll',
                  'setSelection'
              ]
          },
          {
              object: sm,
              methods: [
                  'refresh'
              ]
          }
      ], function(cfg) {
          Ext.Array.each(cfg.methods, function(methodName) {
              Ext.Function.interceptBefore(cfg.object, methodName, function() {
                  sm.setLocked(false);
              });
              Ext.Function.interceptAfter(cfg.object, methodName, function() {
                  sm.setLocked(true);
              });
          });
      });
      me.callParent(arguments);
  },
  /**
	 * @private
	 * Shadowbox 초기화
	 */
  initShadowbox: function() {
      var me = this;
      Shadowbox.init();
  },
  /**
	 * @private
	 * Shadowbox 설정
	 */
  setupShadowbox: function() {
      var me = this,
          shadowboxs = me.el.query('.shadowbox');
      Shadowbox.clearCache();
      Ext.Array.each(shadowboxs, function(shadowbox) {
          Shadowbox.setup(shadowbox, {
              gallery: true
          });
      });
      Shadowbox.thumbnailId = me.id;
  },
  /**
	 * @private
	 * dataview 이벤트 리스너 생성
	 */
  setupViewListeners: function() {
      var me = this;
      me.viewListeners = me.on({
          itemadd: me.onItemAdd,
          scope: me,
          destroyable: true
      });
  },
  /**
	 * @private
	 * selectionmodel 이벤트 리스너 생성
	 */
  setupSelectionModelListeners: function() {
      var me = this;
      me.selectionListeners = me.selModel.on({
          select: me.onSelect,
          deselect: me.onDeselect,
          scope: me,
          destroyable: true
      });
  },
  /**
	 * @private
	 * {@link Ext.view.View} itemmousedown 이벤트리스너 Shadowbox 를 이용한 갤러리 활성화
	 */
  onItemMouseDown: function(record, item, index, e) {
      var me = this,
          mimeType = record.get('mimeType') || record.get('type');
      if (mimeType.indexOf('image') > -1 && Shadowbox.thumbnailId != me.id) {
          me.setupShadowbox();
      }
  },
  /**
	 * @private
	 * dom 의 class 가 포함되어 있는지 확인
	 */
  containsClassName: function(dom, name) {
      var me = this;
      if (dom.classList) {
          return dom.classList.contains(name);
      }
      return dom.className.indexOf(name) > -1;
  },
  /**
	 * @private
	 * {@link Ext.view.View} beforeitemclick 이벤트리스너
	 */
  onBeforeItemClick: function(record, item, index, e) {
      var me = this,
          uploader = me.getUploader(),
          sm = me.getSelectionModel(),
          status = record.get(uploader.statusField),
          target = e.getTarget('div');
      if ((status == 1 || status == 4 || status == 6) && me.containsClassName(target, 'status')) {
          return true;
      } else if (status == 5) {
          if (me.containsClassName(target, 'download')) {
              return true;
          }
          if (me.containsClassName(target, 'status')) {
              return true;
          }
      }
      return false;
  },
  onItemDelete: function(record, item, e) {
      /*var me = this,
          uploader = me.getUploader(),
          sm = me.getSelectionModel(),
          status = record.get(uploader.statusField);
      if ((status == 1 || status == 4) && me.containsClassName(target, 'local')) {
          uploader.removeFile(record.getId());
          Ext.defer(uploader.setUploadButtonDisabled, 1, uploader);
          Ext.defer(uploader.setDeleteButtonDisabled, 1, uploader);
      } else if (status == 5 || status == 6) {
      	sm.setLocked(false);
          sm.select(record, true);
          sm.setLocked(true);
      }*/
  },
  /**
	 * @private
	 * {@link Ext.view.View} itemadd 이벤트핸들러
	 */
  onItemAdd: function(records, index, node) {
      var me = this;
      if (me.thumbnail) {
      	var elWidth = this.getWidth(),
      		elHeight = this.getHeight();
          Ext.Array.each(records, function(record) {
              if (record.get('status') == 1 && record.get('type').indexOf('image') > -1) {
                  if (window.mOxie) {
                      var preloader = new mOxie.Image();
                      preloader.onload = function() {
                          me.suspendLayouts();
                          var dataUrl = preloader.getAsDataURL(this.type, 100);
                          record.set('downloadUrl', dataUrl);
                          if(preloader.width > elWidth && preloader.height > elHeight) {
								preloader.crop(elWidth, elHeight);
							}
							else if(preloader.width > elWidth) {
								preloader.downsize(elWidth, preloader.height, false, true, true);
							}
							else if(preloader.height > elHeight) {
								preloader.downsize(preloader.width, elHeight, false, true, true);
							}
							else {
								record.set('thumbnailUrl', dataUrl);
							}
                          record.commit();
                          me.resumeLayouts(true);
                      };
                      preloader.onresize = function() {
                          record.set('thumbnailUrl', preloader.getAsDataURL(this.type, 100));
                      };
                      preloader.load(record.data.getSource());
                  }
              }
          });
      }
  },
  /**
	 * @private
	 * {@link Ext.selection.Selection} select 이벤트핸들러
	 */
  onSelect : function(sm, record, index) {
		var me = this,
	    	uploader = me.getUploader(),
	        status = record.get(uploader.statusField),
			node = Ext.get(me.getNodeByRecord(record)).down('.status');
		
	    node.addCls('delete');
	},
	
	/**
	 * @private
	 * {@link Ext.selection.Selection} deselect 이벤트핸들러
	 */
	onDeselect : function(sm, record, index) {
		var me = this,
			uploader = me.getUploader(),
			node = Ext.get(me.getNodeByRecord(record)).down('.status');
		
		node.removeCls('delete');
	},
  /**
	 * @private
	 * 파일 업로드 전 호출되는 함수
	 */
  beforeUpload: function(file) {
  	var me = this,
		wrap = me.el.down('.single-file-wrap[dataview-item-id='+file.id+']'),
		status = wrap.down('.status');
	
		if(wrap.getBottom() >= me.el.getBottom()) {
			scrollGap = wrap.getBottom() - me.el.getBottom(); 
			me.el.setScrollTop(me.el.getScrollTop() + scrollGap);
		}
		if(Ext.isIE9m) {
			wrap.addCls('v-progress');
		}
		if(status) {
			status.removeCls('local');
			status.addCls('uploading');
		}
  },
  /**
	 * @private
	 * 파일 업로드 후 호출되는 함수
	 */
  fileUploaded: function(file) {
  	var me = this,
		backgroundColor = me.progressGradientColors[1],
		wrap = me.el.down('.single-file-wrap[dataview-item-id='+file.id+']'),
		status = wrap.down('.status');
	
		wrap.setStyle('background', backgroundColor);
		if(status) {
			status.removeCls('uploading');
			status.addCls('success');
		}
		if(Ext.isIE9m) {
			wrap.removeCls('v-progress');
		}
  },
  /**
	 * @private
	 * 파일업로드 상태를 프로그래스바로 표현함
	 */
  updateProgress: function(percent, file) {
  },
  /**
	 * @private
	 * Shadowbox thumbnailId 초기화
	 */
  refresh: function() {
      var me = this;
      delete Shadowbox.thumbnailId;
      me.callParent(arguments);
  },
  /**
	 * @private
	 * dataveiw 이벤트 제거
	 */
  destroy: function() {
      var me = this;
      Ext.destroy(me.viewListeners);
      Ext.destroy(me.selectionListeners);
      me.bindStore(null);
      me.callParent(arguments);
  }
}, function(clazz) {
  var version = Ext.getVersion();
  if (version.isGreaterThan("5.1.1")) {
      Ext.override(clazz, {
          selectionModel: clazz.prototype.selModel
      });
  }
});

Ext.define('Csrf.Etna.upload.StoreBasedThumbnailUploader', {
	override : 'Etna.upload.StoreBasedThumbnailUploader',
	
	onPluploadBeforeUpload: function(uploader, file) {
      Ext.apply(uploader.settings.headers, _csrfHeaders);
	  this.callParent(arguments);
	}
});


Ext.define('Etna.upload.StoreBasedThumbnailUploader', {
  extend: 'Ext.panel.Panel',
  alias: 'widget.etnastorebasedthumbnailuploader',
  mixins: {
      field: 'Ext.form.field.Field',
      uploader: 'Etna.upload.Uploader'
  },
  statics: {
      suspended: [],
      suspend: function(uploader) {
          this.suspended.push(uploader);
      },
      resume: function() {
          var uploader;
          while ((uploader = this.suspended.pop())) {
              uploader.preInitPlUpload(true);
          }
      }
  },
  requires: [
      'Etna.upload.ui.ThumbnailView'
  ],
  config: {
      /**
		 * @cfg {String} maxFileCount
		 * 첨부파일수 제한
		 */
      maxFileCount: 1,
      /**
		 * @cfg {String} minFileCount
		 * 첨부파일수 제한
		 */
      minFileCount: 0,
	  
	  multiSelection: false, //다중선택 불가하도록.
	  
	  maxFileSize: '200kb', //최대 첨부가능한 사이즈
  },
  useDragDrop: false,
  /**
	 * @cfg {Boolean} isStoreBasedUploader
	 */
  isStoreBasedUploader: true,
  /**
	 * @cfg {String} layout
	 */
  layout: 'card',
  /**
	 * @cfg {Boolean} deferredRender
	 */
  deferredRender: true,
  /**
	 * @cfg {Number} height
	 */
  height: 150,
  /**
	 * @cfg {Number/String/Boolean} bodyBorder
	 */
  bodyBorder: false,
  /**
	 * @cfg {String} browseButtonLabel
	 * Browse 버튼 라벨
	 */
  browseButtonLabel: '#{올리기}',
  /**
	 * @cfg {String} uploadButtonLabel
	 * Upload 버튼 라벨
	 */
  uploadButtonLabel: '#{업로드}',
  /**
	 * @cfg {String} deleteButtonLabel
	 * Delete 버튼 라벨
	 */
  deleteButtonLabel: '#{삭제}',
  /**
	 * @cfg {String} updateButtonLabel
	 * Delete 버튼 라벨
	 */
  updateButtonLabel: '#{수정}',
  /**
	 * @cfg {String} downloadButtonLabel
	 * Download 버튼 라벨
	 */
  downloadButtonLabel: '#{받기}',
  /**
	 * @cfg {String} openButtonLabel
	 * Open 버튼 라벨
	 */
  openButtonLabel: '#{열기}',
  /**
	 * @cfg {String} closeButtonLabel
	 * Close 버튼 라벨
	 */
  closeButtonLabel: '#{닫기}',
  /**
	 * @cfg {String} listUrl
	 * 첨부파일 목록조회 url
	 */
  listUrl: null,
  /**
	 * @cfg {String} downloadUrl
	 * 첨부파일 다운로드 url
	 */
  downloadUrl: null,
  /**
	 * @cfg {String} multifileDownloadUrl
	 * 첨부파일 일괄 다운로드 url
	 */
  multifileDownloadUrl: null,
  /**
	 * @cfg {String} updateUrl
	 * 첨부파일 수정 url
	 */
  updateUrl: null,
  /**
	 * @cfg {String} deleteUrl
	 * 첨부파일 삭제 url
	 */
  deleteUrl: null,
  /**
	 * @cfg {String} emptyTextTpl
	 * Grid View EmptyText Template
	 */
  emptyTextTpl: '<div class="' + Ext.baseCSSPrefix + 'etna-uploader-empty-text-wrap"><div class="' + Ext.baseCSSPrefix + 'etna-uploader-empty-text">{0}</div></div>',
  /**
	 * @cfg {String} progressTotalLabel
	 * 프로그래스바 라벨
	 */
  progressTotalLabel: 'Total:',
  /**
	 * @cfg {String} browseButtonIconCls Browse 버튼 스타일 
	 */
  browseButtonIconCls: Ext.baseCSSPrefix + 'etna-uploader-browse-icon',
  /**
	 * @cfg {String} uploadButtonIconCls Upload 버튼 스타일 
	 */
  uploadButtonIconCls: Ext.baseCSSPrefix + 'etna-uploader-upload-icon',
  /**
	 * @cfg {String} deleteButtonIconCls Delete 버튼 스타일 
	 */
  deleteButtonIconCls: Ext.baseCSSPrefix + 'etna-uploader-delete-icon',
  /**
	 * @cfg {String} updateButtonIconCls Delete 버튼 스타일 
	 */
  updateButtonIconCls: Ext.baseCSSPrefix + 'etna-uploader-update-icon',
  /**
	 * @cfg {String} downloadButtonIconCls Delete 버튼 스타일 
	 */
  downloadButtonIconCls: Ext.baseCSSPrefix + 'etna-uploader-download-icon',
  /**
	 * @cfg {String} closeButtonIconCls Delete 버튼 스타일 
	 */
  closeButtonIconCls: Ext.baseCSSPrefix + 'etna-uploader-close-icon',
  /**
	 * @cfg {Boolean} hideDeleteButton
	 * 삭제버튼 비활성봐 여부
	 */
  hideDeleteButton: false,
  /**
	 * @cfg {Boolean} hideUploadButton
	 * 업로드버튼 비활성봐 여부
	 */
  hideUploadButton: false,
  /**
	 * @cfg {Boolean} hideUpdateButton
	 * 수정버튼 비활성봐 여부
	 */
  hideUpdateButton: false,
  /**
	 * @cfg {Boolean} hideOpenButton
	 * 열기버튼 비활성봐 여부
	 */
  hideOpenButton: false,
  /**
	 * @cfg {Boolean} hideDownloadButton
	 * 다운로드버튼 비활성봐 여부
	 */
  hideDownloadButton: false,
  /**
	 * @cfg {Boolean} hideCloseButton
	 * 닫기버튼 비활성봐 여부
	 */
  hideCloseButton: true,
  /**
	 * @cfg {String} statusField
	 * 상태 필드명
	 */
  statusField: 'status',
  /**
	 * @cfg {String} nameField
	 * 파일명 필드명
	 */
  nameField: 'name',
  /**
	 * @cfg {String} sizeField
	 * 사이즈 필드명
	 */
  sizeField: 'size',
  /**
	 * @cfg {String} mimeTypeField
	 * 파일유형 필드명
	 */
  mimeTypeField: 'mimeType',
  /**
	 * @cfg {String} fileGroupField
	 * 파일그룹 필드명
	 */
  fileGroupField: 'fileGroup',
  /**
	 * @cfg {String/Number} activeItem
	 * 첨부파일 ui 활성화 item / index
	 */
  activeItem: 0,
  /**
	 * @cfg {Boolean} autoLoad
	 * 첨부파일 목록 자동로드 여부
	 */
  autoLoad: true,
  /**
	 * @cfg {String} defaultFileNameDateFormat
	 * 일괄 다운로드 파일명 포맷
	 */
  defaultFileNameDateFormat: 'Y.m.d_H.i.s',
  /**
	 * @cfg {Function} getMultifileDownloadName
	 * 일괄 다운로드 파일명 함수
	 */
  getMultifileDownloadName: null,
  /**
	 * @cfg {Array} ui 클래스와 첨부파일 컴포넌트 이벤트 처리
	 */
  uiRelayEvents: null,
  /**
	 * @property {Array} success 업로드 성공파일
	 * @private
	 */
  success: null,
  /**
	 * @property {Array} failed 업로드 실패파일
	 * @private
	 */
  failed: null,
  /**
	 * @property {Boolean} autoUpload 자동 업로드 여부
	 * @private
	 */
  autoUpload: false,
  /**
	 * @property {Boolean} isShowingStatusBar 파일업로드시 프로그래스바 표현여부
	 * @private
	 */
  isShowingStatusBar: false,
  /**
	 * @property {Ext.minins.Bindable} bind 사용시 바인딩할 프로퍼티 명
	 * @private
	 */
  defaultBindProperty: 'value',
  /**
	 * @property {Array} 첨부파일 컴포넌트 UI 클래스
	 */
  uiClasses: [
      'Etna.upload.ui.ThumbnailView'
  ],
  /**
	 * @property {Boolean} 첨부파일 업로드 진행상태
	 */
  uploading: false,
  /**
	 * @private {Number/String/Array}
	 */
  hideUi: null,
  /**
	 * @constructor
	 * @param {Object} config 설정
	 * store, ui, intercept 함수 생성
	 */
  constructor: function(config) {
      var me = this;
      me.success = [];
      me.failed = [];
      me.files = [];
      me.createStore(config);
      me.createUi(config);
      me.callParent(arguments);
      me.setupStoreListeners();
      me.setupInterceptor();
      if (Ext.isIE9m) {
          me.initPlUpload = Ext.Function.createBuffered(me.initPlUpload, 100);
      }
  },
  /**
	 * @private
	 * 컴포넌트 초기화<p>
	 * 상단의 툴바에 Browse, Upload, Delete 버튼 및 하단 툴바에 프로그래스바, ui 생성 
	 */
  initComponent: function() {
      var me = this;
      Ext.apply(me, {
          /*
		  tbar: {
              itemId: 'upload-tbar',
              items: [{
  					xtype : 'button',
  					itemId : 'closeButton',
  					iconCls : me.closeButtonIconCls,
  					text : me.closeButtonLabel,
  					hidden : true,
  					handler : Ext.Function.bind(me.onClose, me)
  				},me.createUiToggleButton()
              ]
          },
		  */
		  bbar: {
              itemId: 'upload-bbar',
              items: [
              	{
                      xtype: 'button',
                      itemId: 'browseButton',
                      text: me.browseButtonLabel,
                      disabled: true,
                      visibility: true,
                      hidden: me.readOnly
                  },
                  /*{
                      xtype: 'button',
                      itemId: 'uploadButton',
                      text: me.uploadButtonLabel,
                      disabled: true,
                      visibility: true,
                      hidden: me.readOnly,
                      handler: Ext.Function.bind(me.onUpload, me)
                  },*/
                  {
                      xtype: 'button',
                      itemId: 'deleteButton',
                      text: me.deleteButtonLabel,
                      disabled: true,
                      visibility: true,
                      hidden: me.readOnly,
                      handler: Ext.Function.bind(me.onDelete, me)
                  },
                  {
                      xtype: 'button',
                      itemId: 'downloadButton',
                      text: me.downloadButtonLabel,
                      disabled: me.readOnly,
                      disabled: true,
                      visibility: true,
                      handler: Ext.Function.bind(me.onDownload, me)
                  },
                  {
                      xtype: 'button',
                      itemId: 'openButton',
                      text: me.openButtonLabel,
                      hidden: me.readOnly,
                      disabled: true,
                      visibility: true,
                      handler: Ext.Function.bind(me.onOpen, me)
                  }
              ]
          }
      });
      me.initField();
      me.createUploadTasks();
      me.preInitPlUpload();
      me.callParent(arguments);
  },
  /**
	 * @private
	 */
  beforeRender: function() {
      var me = this,
          items = me.getLayoutItems();
      if (isNaN(me.activeItem)) {
          Ext.Array.each(items, function(item) {
              if (item.type == me.activeItem) {
                  me.setActiveItem(item);
                  return false;
              }
          });
      } else {
          me.setActiveItem(items[me.activeItem]);
      }
      me.callParent(arguments);
  },
  /**
	 * @private
	 */
  afterRender: function() {
      var me = this;
      me.callParent(arguments);
      if (!Ext.isEmpty(me.value)) {
          me.load();
      }
  },
  /**
	 * @private
	 * 전달받은 스토어가 없는경우 기본 스토어 생성함
	 */
  createStore: function(config) {
      var me = this;
      if (!config.store) {
          config.store = {
              fields: [
                  {
                      name: me.statusField,
                      type: 'int'
                  },
                  {
                      name: me.nameField,
                      type: 'string'
                  },
                  {
                      name: me.sizeField,
                      type: 'int'
                  },
                  {
                      name: me.mimeTypeField,
                      type: 'string'
                  },
                  {
                      name: me.fileGroupField,
                      type: 'string'
                  }
              ],
              proxy: {
                  type: 'ajax',
                  url: me.listUrl,
                  reader: {
                      type: 'json'
                  }
              },
              filterUpdated: Ext.Function.bind(me.filterUpdated, me)
          };
      }
  },
  /**
	 * @private
	 * ui class 로 지정된 화면을 생성함
	 */
  createUi: function(config) {
      var me = this,
          items = [],
          hideUi = Ext.isEmpty(me.hideUi) ? false : (Ext.isArray(me.hideUi) ? me.hideUi : [
              me.hideUi
          ]),
          ui,
          uiRelayEvents = (config.uiRelayEvents || me.uiRelayEvents),
          relayEvents;
      Ext.Array.each(me.uiClasses, function(className, index) {
          if (!Ext.ClassManager.get(className).prototype.hidden && !Ext.Array.contains(hideUi, index) && !Ext.Array.contains(hideUi, Ext.ClassManager.get(className).prototype.type)) {
              ui = Ext.create(className, {
                  loadMask: config.loadMask,
                  store: config.store,
                  uploader: me,
                  readOnly: me.readOnly,
                  listeners: {
                      activate: me.onUiActivate,
                      scope: me,
                      single: true
                  }
              });
              if (uiRelayEvents) {
                  if (Ext.isArray(uiRelayEvents)) {
                      me.relayEvents(ui, uiRelayEvents);
                  } else {
                      if ((relayEvents = uiRelayEvents[ui.type])) {
                          me.relayEvents(ui, relayEvents);
                      }
                  }
              }
              items.push(ui);
          }
      });
      me.items = items;
  },
  onUiActivate: function(item) {
      var me = this,
          uploader = me.getUploader(),
          emptyText;
      if (!me.items.contains(item)) {
          return;
      }
      if (!me.initialized) {
          me.on('initialized', Ext.Function.bind(me.onUiActivate, me, [
              item
          ], 0), me, {
              single: true
          });
          return;
      }
      if (!me.readOnly) {
          switch (uploader.runtime) {
              case 'flash':
              case 'silverlight':
              case 'html4':
                  emptyText = me.noDragDropAvailableLabel;
                  break;
              case 'html5':
                  emptyText = '<br><font color="red">파일 제한 사이즈 : '+me.maxFileSize+'</font>';
                  break;
          }
          Ext.defer(item.setEmptyText, 1, item, [
              Ext.String.format(me.emptyTextTpl, emptyText)
          ]);
      }
  },
  createUiToggleButton: function() {
      var me = this,
          activeToggle = me.items.length > 1,
          toggle = {
              xtype: 'segmentedbutton',
              itemId: 'toggleButton',
              items: [],
              listeners: {
                  toggle: me.onToggleButtonClick,
                  scope: me
              },
              hidden:true
          };
      if (activeToggle) {
          Ext.Array.each(me.items, function(ui, index) {
              toggle.items.push({
                  xtype: 'button',
                  iconCls: ui.toggleButtonIconCls,
                  type: ui.type,
                  pressed: (index === me.activeItem || ui.type === me.activeItem)
              });
          });
      }
      return toggle;
  },
  /**
	 * @private
	 * 컴포넌트 초기화<p>
	 * 그리드 상단의 툴바에 Browse, Upload, Delete 버튼 및 하단 툴바에 프로그래스바, 컬럼생성
	 */
  createUploadTasks: function() {
      var me = this;
      Ext.apply(me, {
          errorTask: new Ext.util.DelayedTask(me.showErrorMsg, me),
          hideStatusBarTask: new Ext.util.DelayedTask(me.hideStatusBar, me, [
              function() {
                  me.files.length = 0;
                  me.uploading = false;
                  if (!!me.failed.length) {
                      me.showErrorMsg();
                  }
                  me.fireEvent('uploadcompleted', me.success, me.failed);
              }
          ])
      });
  },
  initPluploadFilterValue: function() {
      var me = this,
          uploader = me.getUploader();
      if (uploader) {
          uploader.attachCount = 0;
          uploader.storeFileSize = 0;
      }
  },
  /**
	 * @private
	 * Plupload Init 이벤트핸들러 브라우저 런타임에 따라 드래그 앤 드랍 여부를 emptyText 로 표현
	 */
  onPluploadInit: function(uploader, data) {
      var me = this;
      if (!me.isDestroyed && !me.destroying) {
          me.beforeSetReadOnly(me.readOnly, true);
      }
      me.initPluploadFilterValue();
      me.fireEvent('beforeinitialized', me, uploader);
  },
  /**
	 * @private
	 * @param uploader Pluploader
	 * @param files Pluploader files
	 * Plupload FilesAdded 이벤트핸들러 파일첨부시 파일상태를 그리드에 반영
	 */
  onPluploadFilesAdded: function(uploader, files) {
      var me = this;
      if (me.readOnly || me.enforceReadOnly) {
          return false;
      }
	  var uploaderFileLength = uploader.files.length,
	      fileLength = files.length;
	  
	  //if(uploaderFileLength){
		  	  //if((uploaderFileLength === 0 && fileLength ===  1) || uploaderFileLength){
		  me.updateStore(files);
		  Ext.Array.push(me.files, files);
		  me.updateAttachmentLimit();
		  if (me.autoUpload) {
			  Ext.defer(function(){
				me.onUpload();
			}, 100);
			  
		  }
	  //}
	  me.initPluploadFilterValue();
  },
  /**
	 * @private
	 * @param uploader Pluploader
	 * @param files Pluploader files
	 * Plupload FilesRemoved 이벤트리스너 파일삭제시 파일상태를 그리드에 반영
	 */
  onPluploadFilesRemoved: function(uploader, files) {
      var me = this;
      Ext.Array.each(files, function(file) {
          me.removeFile(file.id);
      });
      me.initPluploadFilterValue();
      me.updateAttachmentLimit();
      Ext.Array.each(files, function(file) {
          Ext.Array.remove(me.files, file);
      });
  },
  /**
	 * @private
	 * @param uploader Pluploader
	 * @param files Pluploader files,
	 * @param status Pluploader File status
	 * Plupload FileUploaded 이벤트리스너 파일업로드 완로시 파일상태를 그리드에 반영
	 */
  onPluploadFileUploaded: function(uploader, file, response) {
      var me = this,
          activeItem = me.getActiveItem(),
          status;
      if (response.status == 200) {
          file.server_error = 0;
          file.status = 5;
          me.success.push(file);
      } else {
          if (response.message) {
              file.msg = '<span style="color: red">' + response.message + '</span>';
          }
          file.server_error = 1;
          me.failed.push(file);
      }
      me.updateFile(file);
      if (activeItem && Ext.isFunction(activeItem.fileUploaded)) {
          activeItem.fileUploaded(file);
      }
  },
  /**
	 * @private
	 * @param uploader Pluploader
	 * @param files Pluploader file
	 * Plupload BeforeUpload 이벤트리스너 파일업로드 시작전 프로그래스바 초기화
	 */
  onPluploadBeforeUpload: function(uploader, file) {
      var me = this,
          activeItem = me.getActiveItem();
      uploader.settings.multipart_params.id = file.id;
	  
	  if (activeItem && Ext.isFunction(activeItem.beforeUpload)) {
          activeItem.beforeUpload(file);
      }
  },
  /**
	 * @private
	 * @param uploader Pluploader
	 * Plupload BeforeUpload 이벤트리스너 파일업로드 시작전 프로그래스바 초기화
	 */
  onPluploadStateChanged: function(uploader) {
      var me = this;
      if (uploader.state == 2) {
          me.hideStatusBarTask.cancel();
          me.fireEvent('uploadstarted', me);
      } else {
          me.hideStatusBarTask.delay(1000);
          me.fireEvent('uploadcomplete', me, me.success, me.failed);
      }
  },
  /**
	 * @private
	 * @param uploader Pluploader
	 * @param files Pluploader file
	 * Plupload UploadProgress 이벤트리스너 파일업로드 상태를 프로그래스바로 표현
	 */
  onPluploadUploadProgress: function(uploader, file) {
      var me = this;
      if (file.server_error) {
          file.status = 4;
      }
      me.updateProgress(file);
  },
  /**
	 * @private
	 * @param uploader Pluploader
	 * @param data Pluploader file
	 * Plupload Error 이벤트리스너 파일첨부 또는 업로드시 오류난 파일에 대한 내용을 {@link Ext.MessageBox} 를 이용해 표현
	 */
  onPluploadError: function(uploader, data) {
      var me = this;
      if (me.blockedPlupload(uploader)) {
          return;
      }
      me.failed.push(data);
      if (!me.uploading) {
          me.errorTask.cancel();
          me.errorTask.delay(30);
      }
  },
  /**
	 * @private
	 * Upload 버튼 클릭 이벤트리스너 첨부파일이 존재하면 프로그래스바를 활성화 하고 파일업로드 함
	 */
  onUpload: function() {
      var me = this,
          uploader = me.getUploader(),
          hasUploadFiles = me.hasUploadFiles.$previous || me.hasUploadFiles;
      if (me.fireEvent('beforeupload') !== false) {
          if (!me.initialized) {
              me.fireEvent('uploadcompleted', me.success, me.failed);
              return;
          }
          me.success.length = 0;
          me.failed.length = 0;
          me.uploading = true;
          if (hasUploadFiles.call(me)) {
                  uploader.disableBrowse(true);
                  me.fireEvent('uploadstart');
                  uploader.settings.multipart_params = Ext.applyIf(Ext.clone(me.getMultipartParams()), {
                      groupId: me.getValue()
                  });
                  uploader.start();
          } else {
              me.uploading = false;
              me.setActionButtonDisabled(true);
              uploader.disableBrowse(false);
              me.fireEvent('uploadcompleted', me.success, me.failed);
          }
      }
  },
  /**
	 * @private
	 * 업데이트 파일이 존재하면 파일정보 업데이트 처리함.
	 */
  onUpdate: function() {
      var me = this,
          updateFiles;
		  //tbar = me.getTbar(),
		  
      if (me.fireEvent('beforeupdate') !== false) {
          if (!me.initialized) {
              me.fireEvent('uploadcompleted', me.success, me.failed);
              return;
          }
          if (me.hasUpdateFiles()) {
              me.setPreventRefresh(true);
              updateFiles = me.getUpdateFiles();
			  /*
              Ext.Array.each(tbar.query('button'), function(button) {
                  button.setDisabled(true);
              });
			  */
              Ext.Ajax.request({
                  url: me.updateUrl,
                  params: {
                      files: updateFiles
                  },
                  success: function(response) {
                      me.setBrowseButtonDisabled(false);
                      me.fireEvent('updatecompleted');
                      me.setPreventRefresh(false);
                  },
                  failure: function() {
                      me.fireEvent('updatefailed');
                      Ext.Msg.alert('Error', "File Update Error");
                      me.setPreventRefresh(false);
                  }
              });
          }
      }
  },
  /**
	 * @private
	 * Delete 버튼 클릭 이벤트리스너 삭제파일이 존재하면 파일삭제 요청함
	 */
  onDelete: function() {
      var me = this,
          deleteFiles;
		  //tbar = me.getTbar(),
		  
      if (me.fireEvent('beforedelete') !== false) {
          if (!me.initialized) {
              me.fireEvent('uploadcompleted', me.success, me.failed);
              return;
          }
          localFiles = me.getTransmitFiles();
          if(localFiles.length){
          	me.removeFile(localFiles[0].getId());
          }
          else{
          	deleteFiles = me.getAttachedFiles();
	            if (deleteFiles.length) {
	                me.setPreventRefresh(true);
					/*
	                Ext.Array.each(tbar.query('button'), function(button) {
	                    button.setDisabled(true);
	                });
					*/
	                Ext.Ajax.request({
	                    url: 'deleteAttachment.do',
	                    params: {
	                        files: deleteFiles
	                    },
	                    success: function(response) {
	                        Ext.Array.each(deleteFiles, function(file) {
	                            me.removeFile(file.getId());
	                        });
	                        me.setBrowseButtonDisabled(false);
	                        me.fireEvent('deletecompleted');
	                        me.setPreventRefresh(false);
	                    },
	                    failure: function() {
	                        me.fireEvent('deletefailed');
	                        Ext.Msg.alert('Error', "File Delete Error");
	                        me.setPreventRefresh(false);
	                    }
	                });
	            }
          }
      }
  },
  /**
	 * @private
	 * 일괄 다운로드 기능
	 */
  onDownload : function() {
		var me = this,
			file = me.getAttachedFiles()[0];
		if(file){
			if(me.fireEvent('beforedownload', file) !== false) {
				Etna.upload.Downloader.download(me.downloadUrl, {
					id : file.get('id')
				});
			}
		}
	},
  /**
	 * @private
	 * 썸네일 팝업에서 보기 기능
	 */
  onOpen: function() {
  	var me = this,
  		shadowbox = me.el.query('.shadowbox')[0];
  	me.getView().setupShadowbox();
	    if(shadowbox){
	    	shadowbox.click();
	    }
  },
  /**
	 * @private
	 * 팝업으로 생성시 닫기버튼 핸들러
	 */
  onClose: function() {
      var me = this;
      if (me.fireEvent('beforeuploaderclose') !== false) {
          me.fireEvent('uploaderclose');
      }
  },
  /**
	 * @private
	 * dataview, grid ui 변경 및 첨부파일 데이터 싱크
	 */
  onToggleButtonClick: function(segmantedButton, button) {
      var me = this,
          layout = me.getLayout(),
          activatedItem = me.getActiveItem(),
          selection = activatedItem.getSelection(),
          store = me.getStore(),
          range = store.getRange(),
          activeItem;
      Ext.Array.each(me.getLayoutItems(), function(item) {
          if (item.type == button.type) {
              activeItem = item;
              return;
          }
      });
      if (activeItem) {
          me.suspendLayouts();
          me.setActiveItem(activeItem);
          store.removeAll();
          me.getStore().loadRecords(range);
          activeItem.setSelection(selection);
          me.resumeLayouts(true);
      }
  },
  /**
	 * @private
	 * {@link Ext.data.Store} add 이벤트리스너 첨부파일이 있는경우 Upload 버튼 활성화 함
	 */
  onStoreAdd: function(store, records, index) {
      var me = this;
      if (Ext.isArray(records) && !!records.length) {
          Ext.Array.each(records, function(record) {
              var status = record.get(me.statusField);
              me.setOpenButtonDisabled(false);
          });
      }
      me.fireEvent('storeadd', store, records);
  },
  /**
	 * @private
	 * {@link Ext.data.Store} update 이벤트리스너 첨부파일이 있으면 업로드 버튼을 활성화 함
	 */
  onStoreUpdate: function(store, record, operation) {
	  /*
      var me = this,
          tbar = me.getTbar(),
          canUpload;
      if (!me.isDestroyed && tbar) {
          canUpload = !tbar.getComponent('uploadButton').disabled;
          if (!canUpload && me.getUploader().state != 2) {
              store.each(function(record) {
                  if (record.get(me.statusColumnDataIndex) == 1) {
                      canUpload = true;
                      return;
                  }
              });
          }
          me.setUploadButtonDisabled(!canUpload);
      }
	  */
  },
  /**
	 * @private
	 * {@link Ext.data.Store} remove 이벤트리스너 첨부파일이 없으면 Upload, Delete 버튼을 비활성화 함
	 */
  onStoreRemove: function(store, record, operation) {
      var me = this;
      if (store && store.getCount && !store.getCount()) {
          me.setDeleteButtonDisabled(true);
          me.setDownloadButtonDisabled(true);
          me.setOpenButtonDisabled(true);
          me.getUploader().total.reset();
          Ext.defer(function() {
              me.getView().refresh();
          }, 10);
      }
      me.fireEvent('storeremove', store, record);
  },
  /**
	 * @private
	 * {@link Ext.data.Store} beforeload 이벤트리스너
	 */
  onStoreBeforeLoad: function(store) {
      var me = this;
      delete me.fireLoadCompleted;
  },
  /**
	 * @private
	 * {@link Ext.data.Store} load 이벤트리스너
	 */
  onStoreLoad: function(store, records) {
      var me = this;
      Ext.Array.each(records, function(record) {
          record.set('status', 5);
          record.commit();
      });
      me.fireLoadCompleted = me.fireEvent('loadcompleted', records);
      me.updateAttachmentLimit();
  },
  /**
	 * @private
	 * 파일목록정보를 스토어에 반영함
	 */
  updateStore: function(files) {
      var me = this;
      Ext.Array.each(files, function(file) {
          me.updateFile(file);
      });
  },
  /**
	 * @private
	 * 파일정보를 스토어에 반영함
	 */
  updateFile: function(file) {
      var me = this,
          store = me.getStore(),
          record = store.getById(file.id),
          re = /(?:\.([^.]+))?$/;
      file.extension = re.exec(file.name).pop();
      if (record) {
          record.set(file);
          record.commit();
      } else {
          record = store.add(file)[0];
      }
  },
  /**
	 * @private
	 * 파일을 스토어 및 Pluploader 에서 삭제함
	 */
  removeFile: function(id) {
      var me = this,
          store = me.getStore(),
          uploader = me.getUploader(),
          file = uploader.getFile(id);
      if (file) {
          uploader.removeFile(file);
      } else {
          store.remove(store.getById(id));
      }
  },
  getActiveItem: function() {
      var me = this,
          layout = me.getLayout(),
          activeItem = layout.getActiveItem();
      if (!activeItem && Ext.isString(me.activeItem)) {
          activeItem = layout.next();
          do {
              if (activeItem.type == me.activeItem) {
                  break;
              }
          } while ((activeItem = activeItem.next()));
      }
      return activeItem;
  },
  setActiveItem: function(item) {
      var me = this,
          layout = me.getLayout();
      layout.setActiveItem(item);
  },
  getLayoutItems: function() {
      var me = this,
          layout = me.getLayout();
      return layout.getLayoutItems();
  },
  /**
	 * @method getDeleteFiles
	 * 삭제파일목록을 리턴함
	 */
  getDeleteFiles: function() {
      var me = this,
      	files = [];
      if (me.readOnly) {
          return files;
      }
		
		Ext.Array.each(me.getStore().getRange(), function(file) {
	        if (file.get('eliminated') === true) {
	            files.push(file);
	        }
	    });
		return files;
  },
  /**
	 * @method getUpdateFiles
	 * 업데이트 파일목록을 리턴함
	 */
  getUpdateFiles: function() {
      var me = this,
          files = [];
      if (!me.readOnly) {
          files = me.getStore().getUpdatedRecords();
      }
      return files;
  },
  /**
	 * @method getTransmitFiles
	 * 첨부파일목록을 리턴함
	 */
  getTransmitFiles: function() {
      var me = this,
          files = [];
      if (!me.readOnly) {
          files = me.getStore().getUnfiltered().createFiltered(Ext.Function.bind(me.filterTransmitted, me)).getRange();
      }
      return files;
  },
  /**
	 * @private
	 */
  filterUpdated: function(file) {
      var me = this;
      if (file.get(me.statusField) === 1 || (file.getEliminated && file.getEliminated())) {
          return false;
      } else {
          return file.dirty === true;
      }
  },
  /**
	 * @private
	 */
  filterTransmitted: function(file) {
      var me = this;
      return file.get(me.statusField) === 1;
  },
  /**
	 * @method getAttachedFiles
	 * 첨부된(저장될) 파일목록을 리턴함
	 */
  getAttachedFiles: function() {
      var me = this,
          deleteFiles = me.getDeleteFiles(),
          files = [];
      Ext.Array.each(me.getStore().getRange(), function(file) {
          if (file.get(me.statusField) === 1 || !Ext.Array.contains(deleteFiles, file)) {
              files.push(file);
          }
      });
      return files;
  },
  /**
	 * @method getSelectionFiles
	 * 선택된 파일목록을 리턴함
	 */
  getSelectionFiles: function() {
      var me = this,
          ui = me.getActiveItem();
      return ui.getSelection();
  },
  /**
	 * @method hasUploadFiles
	 * 첨부파일목록 존재여부를 리턴함
	 */
  hasUploadFiles: function() {
      var me = this;
      return me.getTransmitFiles().length > 0;
  },
  /**
	 * @method hasUpdateFiles
	 * 업데이트파일목록 존재여부를 리턴함
	 */
  hasUpdateFiles: function() {
      var me = this;
      return me.getUpdateFiles().length > 0;
  },
  /**
	 * @method hasUploadFiles
	 * 삭제파일목록 존재여부를 리턴함
	 */
  hasDeleteFiles: function() {
      var me = this;
      return me.getDeleteFiles().length > 0;
  },
  /**
	 * @method hasUploadFiles
	 * 첨부된(저장될)파일목록 존재여부를 리터함
	 */
  hasAttachedFiles: function() {
      var me = this;
      return me.getAttachedFiles().length > 0;
  },
  /**
	 * @method hasSelectionFiles
	 * 선택된 파일목록 존재여부를 리터함
	 */
  hasSelectionFiles: function() {
      var me = this;
      return me.getSelectionFiles().length > 0;
  },
  /**
	 * @method hasAttachedFileCount
	 * 첨부된(저장될) 파일수가 인자값만큼 있는지 검사
	 * @param {Number} count
	 */
  hasAttachedFileCount: function(count) {
      var me = this,
          count = count || 0,
          attachedFileCount = me.getAttachedFiles().length;
      return attachedFileCount >= count;
  },
  /**
	 * @method download
	 * @protected
	 * @param file {@link Ext.data.Model} 첨부파일 모델
	 * 첨부파일을 다운로드 함
	 */
  download: function(file) {
      var me = this;
      if (me.fireEvent('beforedownload', file) !== false) {
          Etna.upload.Downloader.download(me.downloadUrl, {
              id: file.get('id')
          });
      }
  },
  /**
	 * @method upload
	 * @protected
	 * 첨부파일을 업로드 함
	 */
  upload: function() {
      var me = this;
      me.onUpload();
  },
  /**
	 * @method load
	 * @protected
	 * @param config {@link Ext.data.Store} 의 load config
	 * 첨부파일 목록을 조회함
	 */
  load: function(config) {
      var me = this,
          config = config || {},
          params = Ext.apply(Ext.clone(me.getMultipartParams()), {
              groupId: me.getValue()
          });
      if (config.params) {
          Ext.applyIf(config.params, params);
      } else {
          config.params = params;
      }
      me.getStore().load(config);
      me.setDeleteButtonDisabled(false);
      me.setDownloadButtonDisabled(false);
      me.setOpenButtonDisabled(false);
  },
  /**
	 * @private
	 * 파일업로드 상태를 계산하여 상태값을 리턴함
	 */
  calcProgress: function() {
      var me = this,
          uploader = me.getUploader(),
          uploaderTotal = uploader.total,
          files = me.files,
          total = {
              size: 0,
              loaded: 0,
              bytesPerSec: uploaderTotal.bytesPerSec
          },
          file;
      for (i = 0; i < files.length; i++) {
          file = files[i];
          if (file.size !== undefined) {
              total.size += file.origSize;
              total.loaded += file.loaded * file.origSize / file.size;
          } else {
              total.size = undefined;
          }
      }
      if (total.size === undefined) {
          total.percent = files.length > 0 ? Math.ceil(total.uploaded / files.length * 100) : 0;
      } else {
          total.percent = total.size > 0 ? Math.ceil(total.loaded / total.size * 100) : 0;
      }
      return total;
  },
  /**
	 * @private
	 * 파일업로드 상태를 프로그래스바로 표현함
	 */
  updateProgress: function(file) {
  },
  updateAttachmentLimit: function() {
      var me = this,
          store = me.getStore(),
          maxFileCount = me.getMaxFileCount();
      if (maxFileCount && !me.readOnly) {
          me.enforceReadOnly = (store.getCount() >= maxFileCount);
          me.setBrowseButtonDisabled(me.enforceReadOnly);
      }
  },
  /**
	 * @private
	 * 파일첨부 및 업로드 에러파일을 {@link Ext.MessageBox} 를 이용하여 오류정보를 표현함
	 */
  showErrorMsg: function() {
      var me = this,
          msg = '';
      if (!me.isDestroyed && !me.destroying && me.fireEvent('uploadfailed', me.failed) !== false) {
          Ext.Array.each(me.failed, function(data) {
              if (data.code == -500) {
                  msg += Ext.String.format('<span style="color:red">{0}({1})</span></br>', data.response || data.message, data.code);
              } else {
                  msg += Ext.String.format('{0} : <span style="color:red">{1}({2})</span></br>', data.file.name, data.response || data.message, data.code);
              }
          });
          Ext.Msg.alert('Error', msg);
      }
      me.failed.length = 0;
  },
  /**
	 * @private
	 * 파일업로드 상태 프로그래바를 비활성화 함
	 */
  hideStatusBar: function(callback) {
      var me = this,
          bbar = me.getBbar();
		  //tbar = me.getTbar(),
      me.isShowingStatusBar = true;
      me.on('loadcompleted', function() {
          me.setBrowseButtonDisabled(true);
          me.setDeleteButtonDisabled(false);
          me.setDownloadButtonDisabled(false);
          me.setOpenButtonDisabled(false);
      }, me, {
          single: true
      });
      bbar.animate({
          listeners: {
              afteranimate: function() {
                  me.resumeLayouts(true);
                  if (callback) {
                      callback.call(me);
                  }
              }
          }
      });
  },
  /**
	 * @private
	 * {@link Ext.form.field.Field} 의 reset 을 호출하기 전에 첨부파일 관련내용을 초기화 함
	 */
  beforeReset: function() {
      var me = this,
          uploader = me.getUploader();
      if (uploader) {
          uploader.files.length = 0;
      }
      me.success.length = 0;
      me.failed.length = 0;
      me.files.length = 0;
      me.getStore().removeAll();
      me.initPluploadFilterValue();
      me.updateAttachmentLimit();
      me.setActionButtonDisabled(true);
  },
  /**
	 * @private
	 * {@link Ext.form.field.Field} 의 setValue 을 호출하기전에 첨부파일 목록조회를 호출함
	 */
  beforeSetValue: function(value, binding) {
      var me = this,
          isEmptyValue = Ext.isEmpty(value);
      if (!binding && me.value != value) {
          if (isEmptyValue && me.getStore().getCount() > 0) {
              me.beforeReset();
          } else if (me.autoLoad && !isEmptyValue) {
              me.load({
                  params: {
                      groupId: value
                  }
              });
          }
      }
      return me;
  },
  /**
	 * @private
	 * {@link Ext.form.field.Base} 의 setReadOnly 을 호출하기전에 툴바의 visible 처리함
	 */
  beforeSetReadOnly: function(value, force) {
      var me = this,
          uploader = me.getUploader(),
          layouts, flush, bbar, hidableBbar;
		  //tbar, hidableTbar,
		  
      if (!me.rendered) {
          if (!me.blockedSetReadOnly && (force || me.readOnly != value)) {
              me.blockedSetReadOnly = true;
              Ext.Logger.log('beforeSetReadOnly function can be called after initialized');
              me.on('initialized', Ext.Function.bind(me.beforeSetReadOnly, me, [
                  value
              ], 0), me, {
                  single: true
              });
          }
          return;
      }
      delete me.blockedSetReadOnly;
      if (!!force || me.readOnly != value) {
          me.readOnly = value;
          // tbar = me.getTbar();
		  bbar = me.getBbar();
		  
          layouts = me.getLayoutItems();
          me.suspendLayouts();
          me.setBrowseButtonDisabled(value);
		  /*
          Ext.Array.each(tbar.query('button[visibility=true]'), function(btn) {
              var visibility = value;
              if (!visibility) {
                  visibility = me[Ext.String.format('hide{0}', Ext.String.capitalize(btn.itemId))];
              }
              btn.setVisible(!visibility);
          });
		  */
          if (me.initialized) {
              me.getMoxieElement().setVisibility(!value);
          }
		  
		  hidableBbar = bbar.query('button[hidden=false]');
          if (value) {
              hidableBbar = hidableBbar.length == 0;
          } else {
              hidableBbar = hidableBbar.length > 0;
          }
          if (hidableBbar) {
              bbar.setVisible(!value);
          }
		  /*
          hidableTbar = tbar.query('button[hidden=false]');
          if (value) {
              hidableTbar = hidableTbar.length == 0;
          } else {
              hidableTbar = hidableTbar.length > 0;
          }
          if (hidableTbar) {
              tbar.setVisible(!value);
          }
		  */
          Ext.Array.each(layouts, function(layout) {
              var isVisible = layout.isVisible();
              if (!isVisible) {
                  Ext.suspendLayouts();
                  layout.setPreventRefresh(true);
              }
              if (isVisible && !flush && (flush = layout.setReadOnly(value))) {
                  flush = {
                      isRoot: true
                  };
              } else {
                  layout.setReadOnly(value);
              }
              layout.setReadOnly(value);
              layout.emptyTextVisible(!value);
              if (!isVisible) {
                  layout.setPreventRefresh(false);
                  Ext.resumeLayouts();
              }
          });
          me.resumeLayouts(flush);
      }
  },
  /**
	 * @method getView
	 * @private
	 * 현재 활성화 된 uploader ui view 를 리턴함 
	 */
  getView: function() {
      var me = this,
          activeItem = me.getActiveItem();
      return activeItem.getView();
  },
  /**
	 * @method getStore
	 * @private
	 * 현재 활성화 된 uploader ui store 를 리턴함 
	 */
  getStore: function() {
      var me = this,
          activeItem = me.getActiveItem();
      return activeItem.getStore();
  },
  /**
	 * @method getBrowseButtonId
	 * @private
	 * 파일선택 버튼 엘리먼트 아이디를 리턴함 
	 */
  getBrowseButtonId: function() {
      var me = this;
      return me.getBrowseButton().getId();
  },
  /**
	 * @method getBrowseButton
	 * @private
	 */
  getBrowseButton: function() {
      var me = this;
      return me.getBbar().getComponent('browseButton');
  },
  /**
	 * @method getContainerId
	 * @private
	 */
	 /*
  getContainerId: function() {
      var me = this,
          tbar = me.getTbar();
      return tbar.el.down('.x-box-target').getId();
  },
  */
  /**
	 * @method getDropElement
	 * @private
	 * 드래그 앤 드랍 엘리먼트 아이디를 리턴함 
	 */
  getDropElementId: function() {
      var me = this;
      return me.body.el.id;
  },
  /**
	 * @method getPluploadFilter
	 * @private
	 * plupload filter 추가 
	   */
  getPluploadFilter: function() {
      var me = this,
          filters = me.mixins.uploader.getPluploadFilter.call(me);
      return Ext.apply(filters, {
          max_file_count: me.getMaxFileCount()
      });
  },

  /**
	 * @method getTbar
	 * @private
	 */
	 /*
  getTbar: function() {
      var me = this;
      return me.getDockedComponent('upload-tbar');
  },
  */
  /**
	 * @method getBbar
	 * @private
	 */
  getBbar: function() {
      var me = this;
      return me.getDockedComponent('upload-bbar');
  },
  /**
	 * @method setActionButtonDisabled
	 * @private
	 * 업로드, 수정, 삭제버튼 활성화 상태를 변경함 
	 */
  setActionButtonDisabled: function(disable) {
      var me = this;
      me.setDeleteButtonDisabled(disable);
      me.setDownloadButtonDisabled(disable);
      //me.setUploadButtonDisabled(disable);
      me.setOpenButtonDisabled(disable);
  },
  /**
	 * @method setDeleteButtonDisabled
	 * @private
	 * delete 버튼 활성화 상태를 변경함 
	 */
  setDeleteButtonDisabled: function(disable) {
      var me = this,
          deleteButton = me.getBbar().getComponent('deleteButton');
      if (disable === undefined || disable === null) {
          disable = true;
      }
      deleteButton.setDisabled(disable);
  },
  /**
	 * @method setUploadButtonDisabled
	 * @private
	 * upload 버튼 활성화 상태를 변경함 
	 */
	/*setUploadButtonDisabled : function(disable) {
		var me = this,
			uploadButton = me.getBbar().getComponent('uploadButton');
		
		if(disable === undefined || disable === null) {
			disable = !(me.hasUploadFiles() || me.hasDeleteFiles());
		}
		uploadButton.setDisabled(disable);
	},*/
  /**
	 * @method setDownloadButtonDisabled
	 * @private
	 * download 버튼 활성화 상태를 변경함 
	 */
  setDownloadButtonDisabled: function(disable) {
      var me = this,
          downloadButton = me.getBbar().getComponent('downloadButton');
      if (disable === undefined || disable === null) {
          disable = !me.hasDeleteFiles();
      }
      downloadButton.setDisabled(disable);
  },
  /**
	 * @method setOpenButtonDisabled
	 * @private
	 * download 버튼 활성화 상태를 변경함 
	 */
  setOpenButtonDisabled: function(disable) {
      var me = this,
          openButton = me.getBbar().getComponent('openButton');
      if (disable === undefined || disable === null) {
          disable = !me.hasDeleteFiles();
      }
      openButton.setDisabled(disable);
  },
  /**
	 * @method setCloseButtonDisabled
	 * @private
	 * close 버튼 활성화 상태를 변경함 
	 */
	 /*
  setCloseButtonDisabled: function(disable) {
      var me = this,
          closeButton = me.getTbar().getComponent('closeButton');
      closeButton.setDisabled(disable);
  },
  */
  /**
	 * @method setHideDeleteButton
	 * @param {Boolean} value 숨김여부
	 * delete 버튼 숨김 상태 변경 
	 */
  setHideDeleteButton: function(value) {
      var me = this,
          deleteBtn = me.getBbar().getComponent("deleteButton");
      me.hideDeleteButton = value;
      deleteBtn.setHidden(value);
  },
  /**
	 * @method setHideUploadButton
	 * @param {Boolean} value 숨김여부
	 * upload 버튼 숨김 상태 변경 
	 */
  setHideUploadButton: function(value) {
      var me = this,
          uploadBtn = me.getBbar().getComponent("uploadButton");
      me.hideUploadButton = value;
      uploadBtn.setHidden(value);
  },
  /**
	 * @private
	 * uploader ui 의 refresh 동작 여부를 변경함
	 */
  setPreventRefresh: function(value) {
      var me = this,
          layoutItems = me.getLayoutItems();
      Ext.Array.each(layoutItems, function(item) {
          if (Ext.isFunction(item.setPreventRefresh)) {
              item.setPreventRefresh(value);
          }
      });
  },
  /**
	 * @private
	 * value, readOnly, reset 의 seeter 함수를 인터셉트 함수를 생성함 
	 */
  setupInterceptor: function() {
      var me = this;
      Ext.Function.interceptBefore(me, 'setValue', me.beforeSetValue, me);
      Ext.Function.interceptBefore(me, 'setReadOnly', me.beforeSetReadOnly, me);
      me.getDownloadFiles = Ext.Function.bind(me.getSelectionFiles, me);
      me.hasDownloadFiles = Ext.Function.bind(me.hasSelectionFiles, me);
  },
  /**
	 * @private
	 * store 이벤트 리스너 드록 
	 */
  setupStoreListeners: function() {
      var me = this,
          layoutItems = me.getLayoutItems();
      me.storeListeners = [];
      Ext.Array.each(layoutItems, function(item) {
          me.storeListeners.push(item.getStore().on({
              add: me.onStoreAdd,
              remove: me.onStoreRemove,
              beforeload: me.onStoreBeforeLoad,
              load: me.onStoreLoad,
              scope: me,
              destroyable: true
          }));
      });
  },
  /**
	 * @private
	 */
  setAutoLoad: function(value) {
      var me = this;
      if (me.autoLoad != value) {
          me.autoLoad = value;
      }
  },
  /**
	 * @method selectFiles
	 * @param {Array} files 선택할 파일목록
	 * @param {Boolean} keepExisting 기존선택 파일 유지여부
	 * @param {Boolean} suppressEvent 이벤트 발생여부
	 */
  selectFiles: function(files, keepExisting, suppressEvent) {
      var me = this,
          ui = me.getActiveItem();
      ui.select(files, keepExisting, suppressEvent);
  },
  /**
	 * @method selectAllFiles
	 * @param {Boolean} suppressEvent 이벤트 발생여부
	 */
  selectAllFiles: function(suppressEvent) {
      var me = this,
          ui = me.getActiveItem();
      ui.selectAll(suppressEvent);
  },
  /**
	 * @method deselectFiles
	 * @param {Array} files 선택취소할 파일목록
	 * @param {Boolean} suppressEvent 이벤트 발생여부
	 */
  deselectFiles: function(files, suppressEvent) {
      var me = this,
          ui = me.getActiveItem();
      ui.deselect(files, suppressEvent);
  },
  /**
	 * @method deselectAllFiles
	 * @param {Boolean} suppressEvent 이벤트 발생여부
	 */
  deselectAllFiles: function(suppressEvent) {
      var me = this,
          ui = me.getActiveItem();
      ui.deselectAll(suppressEvent);
  },
  /**
	 * @private
	 */
  blockedPlupload: function(uploader) {
      var me = this,
          hiddenOwnerCt;
      if (!me.initialized && (hiddenOwnerCt = me.up('[hidden=true]'))) {
          me.blockedinitPlUpload = true;
          hiddenOwnerCt.on('show', function() {
              uploader.init();
          }, me, {
              single: true
          });
          return true;
      }
      return false;
  },
  /**
	 * @private
	 * pluploader 를 제거하고 등록한 이벤트 제거 및 task 를 취소한다.
	 */
  destroy: function() {
      var me = this,
          uploader = me.getUploader();
      me.errorTask.cancel();
      me.hideStatusBarTask.cancel();
      Ext.Array.each(me.storeListeners, function(listeners) {
          Ext.destroy(listeners);
      });
      if (me.initialized) {
          if (uploader.runtime == 'html5') {
              me.dragMaskEl.destroy();
              me.dragMaskTask = undefined;
          }
          uploader.destroy();
      }
      me.store = undefined;
      me.callParent(arguments);
  }
}, function(clazz) {
  var plupload = window.plupload;
  if (!plupload) {
      Ext.defer(arguments.callee, 100, this, [
          clazz
      ]);
      return;
  }
  if (Ext.isIE9) {
      Ext.override(clazz, {
          initPlUpload: function(initializer) {
              var me = this;
              me.callParent([
                  initializer || function(fn, scope) {
                      Ext.defer(function() {
                          fn.call(scope);
                          Ext.Logger.log(me.id + ' plupload init function called');
                      }, 10);
                  }
              ]);
          }
      });
  }
  Ext.override(clazz, {
      preInitPlUpload: function(force) {
          var me = this;
          me.callParent(arguments);
          if (!me.autoInit) {
              Etna.upload.StoreBasedUploader.suspend(me);
          }
      }
  });
  clazz.addFileFilter('max_file_count', function(maxFileCount, file, skipMessage) {
      var uploader = this.getOption('uploader'),
          store, count;
      if (uploader.isStoreBasedUploader) {
          store = uploader.getStore();
          count = store.getCount();
          if (maxFileCount && (count + (++this.attachCount) > maxFileCount)) {
              if (!uploader.enforceReadOnly && !uploader.readOnly) {
				  for(var i=0, len = this.files.length; i<len; i++){
					  this.removeFile(this.files[0]);
				  }
					
				  if (skipMessage !== true) {
                      this.trigger('Error', {
                          code: Etna.upload.Uploader.FILE_COUNT_LIMIT,
                          message: plupload.translate('File count limit'),
                          file: file
                      });
                  }
              }
              this.attachCount--;
              return false;
          }
      }
      return true;
  });
  clazz.addFileFilter('total_file_size', function(totalFileSize, file, skipMessage) {
      var me = this,
          uploader = me.getOption('uploader'),
          store, storeFileSize;
      if (uploader.isStoreBasedUploader) {
          store = uploader.getStore();
          storeFileSize = this.storeFileSize;
          totalFileSize = plupload.parseSize(totalFileSize);
          if (totalFileSize) {
              if (!storeFileSize) {
                  Ext.Array.each(store.getRange(), function(f) {
                      storeFileSize += f.get('size');
                  });
              }
              if (storeFileSize + file.size > totalFileSize) {
                  if (skipMessage !== true) {
                      this.trigger('Error', {
                          code: plupload.FILE_SIZE_ERROR,
                          message: plupload.translate('Total File size error.'),
                          file: file
                      });
                  }
                  return false;
              }
              this.storeFileSize = storeFileSize + file.size;
          }
      }
      return true;
  });
});

Ext.define('Cmmn.override.upload.ui.ThumbnailView', {
  override: 'Etna.upload.ui.ThumbnailView',
  thumnailUrl: 'downloadThumbnail.do',
  thumnailDownloadUrl: 'downloadAttachment.do'
});

Ext.define('Cmmn.override.upload.StoreBasedThumbnailUploader', {
  override: 'Etna.upload.StoreBasedThumbnailUploader',
  uploadUrl: 'uploadAttachment.do',
  downloadUrl: 'downloadAttachment.do',
  multifileDownloadUrl: 'downloadAttachments.do',
  listUrl: 'smartsuit.ui.etnajs.cmmn.CommonController.getAttachments',
  deleteUrl: 'smartsuit.ui.etnajs.cmmn.CommonController.removeAttachment',
  looseComplete: true,
  constructor: function(config) {
      var me = this;
      me.callParent(arguments);
      me.on({
          uploadcompleted: me.onUploadCompleted,
          uploadfailed: me.onUploadFailed,
          attachmentsynccompleted: me.onAttachmentSyncCompleted,
          scope: me
      });
  },
  createStore: function(config) {
      var me = this;
      if (!config.store) {
          config.store = {
              fields: [
                  {
                      name: me.statusField,
                      type: 'int'
                  },
                  {
                      name: me.nameField,
                      type: 'string'
                  },
                  {
                      name: me.sizeField,
                      type: 'int'
                  },
                  {
                      name: me.mimeTypeField,
                      type: 'string'
                  }
              ],
              proxy: {
                  type: 'direct',
                  api: (function() {
                      var updateApi;
                      if (me.updateUrl) {
                          updateApi = {
                              update: me.updateUrl
                          };
                      }
                      return Ext.apply({
                          read: me.listUrl,
                          destroy: me.deleteUrl
                      }, updateApi);
                  }()),
                  reader: {
                      type: 'json'
                  }
              }
          };
      }
  },
  onUpload: function() {
      var me = this,
          parentOnUpload = arguments.callee.$previous;
      if (!me.initialized) {
          me.fireEvent('uploadcompleted', me.success, me.failed);
          return;
      }
	  me.setDeleteButtonDisabled(true);
      me.checkBindValue();
      me.onDelete();
      me.doSync(function() {
          parentOnUpload.call(me);
      });
  },
  checkBindValue: function() {
      var me = this;
      if (me.hasUploadFiles() && Ext.isEmpty(me.getValue())) {
          me.setValue(new Ext.data.identifier.Uuid().generate(), true);
          me.fireEvent('bindingvaluechange', me.getValue());
      }
  },
  upload: function() {
      var me = this;
      me.deferred = Ext.create('Deft.promise.Deferred');
      me.onUpload();
      return me.deferred.promise;
  },
  doSync: function(callback, fromButton) {
      var me = this,
          store = me.getStore();
		  // tbar = me.getDockedComponent('upload-tbar');
      if (me.fireEvent('beforeattachmentsync') !== false) {
		  /*
          Ext.Array.each(tbar.query('button[disabled=false]'), function(button) {
              button.setDisabled(true);
          });
		  */
          if (me.getUpdateFiles().length > 0 || me.getDeleteFiles().length > 0) {
              me.setPreventRefresh(true);
              store.sync({
                  success: function(batch, options) {
                      me.fireEvent('attachmentsynccompleted', fromButton);
                      if (Ext.isFunction(callback)) {
                          callback.call(me);
                      }
                      me.setDeleteButtonDisabled(true);
                      me.setDownloadButtonDisabled(true);
                      me.setOpenButtonDisabled(true);
         //             me.setUploadButtonDisabled(true);
                      me.setPreventRefresh(false);
                  },
                  failure: function(batch, options) {
                      me.fireEvent('attachmentsyncfailed');
                      if (me.deferred) {
                          me.deferred.reject('파일 업로드 오류');
                      }
                      me.setPreventRefresh(false);
                  }
              });
          } else {
              if (Ext.isFunction(callback)) {
                  callback.call(me);
              }
          }
      }
  },
  onUpdate: function(button) {
      var me = this,
          updateFiles = me.getUpdateFiles();
      if (me.fireEvent('beforeupdate') !== false) {
          if (updateFiles.length > 0) {
              me.setPreventRefresh(true);
              Ext.Array.each(updateFiles, function(file) {
                  file.set('fileGroup', me.getValue(), {
                      silent: true
                  });
              });
              if (button && button.isButton) {
                  me.doSync(null, true);
              }
          }
      }
  },
  onDelete: function(button) {
      var me = this,
          deleteFiles = me.getDeleteFiles(),
          localFiles = me.getTransmitFiles();
      if(button && localFiles.length){
      	me.removeFile(localFiles[0].getId());
      }
      else {
	        if(button && deleteFiles.length == 0){
	        	deleteFiles = me.getAttachedFiles();
	        }
	        if (me.fireEvent('beforedelete') !== false) {
	            if (deleteFiles.length > 0) {
	                me.setPreventRefresh(true);
	                Ext.Array.each(deleteFiles, function(file) {
	                    file.set('eliminated', true, {
	                        silent: true
	                    });
	                });
	                if (button && button.isButton) {
	                    me.doSync(null, true);
	                }
	            }
	        }
      }
  },
  onStoreAdd: function(store, records, index) {
      var me = this;
	  //if(me.autoUpload){
		//  me.upload();
	  //}else{
		  me.callParent(arguments);
		  if (Ext.isArray(records) && !!records.length) {
		//	me.setUploadButtonDisabled(false);
			  Ext.Array.each(records, function(record) {
				  var status = record.get(me.statusField);
				  if (status == 1) {
					me.setDeleteButtonDisabled(false);
				  }
				  if (status == 6) {
		//			  me.setUploadButtonDisabled(false);
					  return false;
				  }
			  });
		  }  
	 // }
  },
  onAttachmentSyncCompleted: function(fromButton) {
      var me = this;
	  //,
        //  tbar = me.getDockedComponent('upload-tbar');
      if (fromButton) {
          me.load({
              params: {
                  groupId: me.getValue()
              },
              callback: function(records) {
                  if (!me.fireLoadCompleted) {
                      me.fireEvent('loadcompleted', records);
                  }
              }
          });
          me.setBrowseButtonDisabled(false);
       /*   Ext.Array.each(tbar.getComponent('toggleButton').getRefItems(), function(button) {
              button.setDisabled(false);
          });
		  */
      }
  },
  onUploadCompleted: function() {
      var me = this,
          successHandler = function() {
              me.deferred.resolve('파일 업로드 성공', me.success, me.failed);
			  me.setDeleteButtonDisabled(false);
          },
          failureHandler = function() {
              me.onUploadFailed();
			  me.setDeleteButtonDisabled(false);
          };
      if (!me.initialized) {
          successHandler();
          return;
      }
 //     me.setUploadButtonDisabled(true);
      me.load({
          params: {
              groupId: me.getValue()
          },
          callback: function(records) {
              me.setBrowseButtonDisabled(false);
              if (!me.fireLoadCompleted) {
                  me.fireEvent('loadcompleted', records);
              }
          }
      });
      if (me.deferred) {
          if (!me.looseComplete && !!me.failed.length) {
              failureHandler();
          } else {
              successHandler();
          }
      }
  },
  onUploadFailed: function() {
      var me = this;
      if (me.deferred) {
          me.deferred.reject('파일 업로드 오류', me.success, me.failed);
      }
  }
  /*
  ,
  hasUploadFiles: function() {
      var me = this;
      return (me.callParent(arguments) || me.hasDeleteFiles() || me.hasUpdateFiles());
  }
  */
});
/* 웹접근성 작업내역 */
//파일 다운로더 iframe에 title 추가
//김형민 프레임 제목 미제공  미제공 pdf#42
Ext.define('Etna.upload.Downloader', {
	override : 'Etna.upload.Downloader',
	frameTpl : [
        '<div id="{id}" data-ref="downloadFrameEl" tabindex="-1" style="display:none;width:0px;height:0px;">',
        	'<iframe id="{id}-iframeEl" data-ref="iframeEl" tabindex="-1" frameBorder="0" title="다운로더"> ',
        		'<html><body>',
        		'</body></html>',
    		'</iframe>',
    	'</div>'
	]
});
//Tree column에 대한 alt 추가 김형민
//김형민 대체텍스트  미제공 pdf#19
Ext.define('Ext.tree.Column', {
	extend: 'Ext.tree.Column',

    cellTpl: [
        '<tpl for="lines">',
            '<img alt ="icon" src="{parent.blankUrl}" class="{parent.childCls} {parent.elbowCls}-img ',
            '{parent.elbowCls}-<tpl if=".">line<tpl else>empty</tpl>" role="presentation"/>',
        '</tpl>',
        '<img alt ="icon" src="{blankUrl}" class="{childCls} {elbowCls}-img {elbowCls}',
            '<tpl if="isLast">-end</tpl><tpl if="expandable">-plus {expanderCls}</tpl>" role="presentation"/>',
        '<tpl if="checked !== null">',
            '<input type="button" {ariaCellCheckboxAttr}',
                ' class="{childCls} {checkboxCls}<tpl if="checked"> {checkboxCls}-checked</tpl>"/>',
        '</tpl>',
        '<img alt ="icon" src="{blankUrl}" role="presentation" class="{childCls} {baseIconCls} ',
            '{baseIconCls}-<tpl if="leaf">leaf<tpl else>parent</tpl> {iconCls}"',
            '<tpl if="icon">style="background-image:url({icon})"</tpl>/>',
        '<tpl if="href">',
            '<a href="{href}" role="link" target="{hrefTarget}" class="{textCls} {childCls}">{value}</a>',
        '<tpl else>',
            '<span class="{textCls} {childCls}">{value}</span>',
        '</tpl>'
    ]
});
//Panel에 대한 img alt 추가 김형민
//김형민 대체텍스트  미제공 pdf#19
Ext.define('Ext.panel.Tool', {
    extend: 'Ext.panel.Tool',
    renderTpl: [
        '<img id="{id}-toolEl" data-ref="toolEl" src="{blank}" class="{baseCls}-img {baseCls}-{type}' +
            '{childElCls}" role="presentation" alt="{type}"/>'
    ]
});
// title을 div에서 h4로 변경 김형민
//콘텐츠 블록 제목 미흡 pdf#41
Ext.define('Ext.panel.Title', {
    extend: 'Ext.panel.Title',
    renderTpl: 
    	 '<tpl if="iconMarkup && iconBeforeTitle">{iconMarkup}</tpl>' +
        
        '<h4 id="{id}-textEl" data-ref="textEl" class="{textCls} {textCls}-{ui} {itemCls}{childElCls}" unselectable="on"' +
            '<tpl if="headerRole">' +
                ' role="{headerRole}"' +
            '</tpl>' +
        '>{text}</h4>' +
        '<tpl if="iconMarkup && !iconBeforeTitle">{iconMarkup}</tpl>',
        
});

//검색 조건에 from ~ to와 같이 라밸이 없는 검색 조건에 대해서 title에 값 추가 김형민
//pdf#49김형민 부적절한 서식 레이블 제공
Ext.define('Ext.form.field.Date', {
    extend: 'Ext.form.field.Date',
    onRender : function (){
    	this.callParent();
    	var bindValue = ''
    	var parents = this.up('fieldcontainer');
    	
    	if(!this.config.fieldLabel && parents && parents.fieldLabel && this.config.bind && this.config.bind.value ){
    		bindValue =  this.config.bind.value.toString().toLowerCase();
    		if(bindValue && (bindValue.indexOf('from') != -1 || bindValue.indexOf('to') != -1 || bindValue.indexOf('start') != -1 || bindValue.indexOf('end') != -1)){
    			var suffix ='';
    			if (bindValue.indexOf('from') != -1 || bindValue.indexOf('start') != -1){
    				suffix  = '검색 시작일'
    			}else{
    				suffix  = '검색 종료일'
    			}
    			this.el.query('input')[0].setAttribute('title',parents.fieldLabel+ " "+ suffix)
    		}
    	}
    }
});


//leftmenu의 treeview에 대한 enter 처리 김형민 키보드 이용불가 pdf#30
Ext.define('Kepco.override.TreeView', {
	override: 'Ext.tree.View',
	onItemKeyDown: function(record, item, index, e ,eOpts) {
		if(e.keyCode === 13 && record) {
			var menuCode = Mdi.store.Menu.getRoot().findChild('id', record.getId(), true);
//			this.getBubbleParent().fireEvent('openMenu', menuCode);
			this.getBubbleParent().controller.onMdiLeftMenuOpenUsingKeyboard(this, record);
		}
	}
});
// grid에서 선택 가능한 셀중, gridcolumn의 tdcls가 link인 항목만 해당하는 코드(etnadataactioncolumn은 제외) 김형민
// 2021.03.23 오현석 과장 전달내용 수정 - 전체 override
Ext.define('Kepco.override.GridView', {
	override: 'Ext.grid.Panel',
	renderTpl: [
		'<div class="scr-notifier" tabindex="0" title="ALT + 방향키로 이동가능. 상세 이동은 ALT + ENTER"></div>',
		'{% this.renderDockedItems(out,values,0); %}',
		'<div id="{id}-body" data-ref="body" class="{baseCls}-body<tpl if="bodyCls"> {bodyCls}</tpl>',
		' {baseCls}-body-{ui}<tpl if="uiCls">',
		'<tpl for="uiCls"> {parent.baseCls}-body-{parent.ui}-{.}</tpl>',
		'</tpl>{childElCls}"',
		'<tpl if="bodyRole"> role="{bodyRole}"<tpl else> role="presentation"</tpl>',
		'<tpl if="bodyStyle"> style="{bodyStyle}"</tpl>>',
		'{%this.renderContainer(out,values);%}',
		'</div>',
		'{% this.renderDockedItems(out,values,1); %}'
	],
	
	listeners:{
		itemKeyDown: function(view, record, item, index, e ) {
			if(e.keyCode === 13 && record) { 
				var td = e.target;
				var dummyEvent = new Ext.event.Event('click');
					
				// 입찰/계약 -> 입찰진행 -> 공동수급협정 (그리드 내 공고번호) 에서는 동작 안함.
				var currentColumn = view.getColumnManager().getColumns()[td.cellIndex];
				dummyEvent.position = { column: currentColumn };
				this.getBubbleParent().fireEvent('cellclick', view, td, td.cellIndex, record, td.parentElement, index, dummyEvent);
			}
		}
	},
	onRender: function() {
		var summaryText = '';
		var targetItems = this.items.items;
		
		for(var i=0; i< targetItems.length; i++) {
			var item = targetItems[i];
			if(item.xtype === 'gridpanel') {
				var columns = item.columns;
				for (var j=0; j<columns.length; j++) {
					summaryText += columns[j].text;
					if(j <columns.length-1) {
						summaryText += ', ';
					}
				}
			}
		}
		if(summaryText !== '') {
			summaryText = summaryText + '로 구성';
			this.el.dom.setAttribute('aria-label', summaryText);
		}
		this.callParent();
		
		// 불필요한 notifier 삭제
		if (this.ownerGrid !== this) {
			var notifiers = this.el.query('.scr-notifier');
			for (var i = 0; i < notifiers.length; i++) {
				var notifier = notifiers[i];
				this.el.removeChild(notifier);
			}
		}
		
		this._applyCollapseButtonAltText();
	},
	_applyCollapseButtonAltText : function() {
		if (this.config.collapsible) {
			var dockBtnImg = this.el.query('img.x-tool-collapse-top, img.x-tool-expand-bottom')[0];
			if (dockBtnImg) {
				var panelText = ((this.title) ? this.title : '') + ' 패널';
				var stateText = (!this.collapsed) ? ' 접기' : ' 펼치기';
				dockBtnImg.setAttribute('alt', panelText + '의 ' + stateText+ '버튼');
				// 타이틀 추가
				var parentNode = dockBtnImg.parentNode;
				parentNode.setAttribute('title', (this.title + (!this.collapsed ? ' 접기' : ' 펼치기')));
				parentNode.tabIndex = 0;
				//Keydown 이벤트 추가
				if(!parentNode.getAttribute('data-hasKeyDownEvent')){
						parentNode.addEventListener('keydown', function(event) {
							if(event.keyCode === 13) {
								parentNode.setAttribute('data-hasKeyDownEvent', true);
								if(!this.collapsed) {
									this.collapse();
									return;
								}
								this.expand();
							}
						}.bind(this));
				}
			}
		}
	},
	collapse : function(e, a) {
		this.callParent(e, a);
		this._applyCollapseButtonAltText();
	},
	expand : function(a) {
		this.callParent(a);
		this._applyCollapseButtonAltText();
	}
	/*,onFocusLeave: function(event, element, component) {
		this.callParent(arguments);
		
		if(this.getBubbleParent() && this.getBubbleParent().getItemId() === 'vendorPresidentGrid') {
			
			var grid = this.getBubbleParent();
			var gridPanel = grid.getBubbleParent();
			if(!gridPanel.nextSibling().hidden) {
				return;
			}
			gridPanel.up().query('#vendorInfoNextBtn')[0].el.dom.setAttribute('tabindex','0');
			gridPanel.up().query('#vendorInfoNextBtn')[0].el.dom.focus();
		}
	}*/
});


//Popup에 대한 포커스 이동 김형민 
Ext.define('Kepco.override.Panel', {
	override: 'Ext.panel.Panel',
	onShowComplete: function(cb, scope) {
		Ext.Component.prototype.onShowComplete.call(this,cb,scope);
		if(this.ui =='popup' || this.ui =='default'){
			if(this.query('combo[hidden=false], button[hidden=false], textfield[hidden=false], check[hidden=false], radio[hidden=false]')[0])
				this.query('combo[hidden=false], button[hidden=false], textfield[hidden=false], check[hidden=false], radio[hidden=false]')[0].focus();
		}
	}
});
//Popup에 대한 포커스 이동 김형민
Ext.define('Kepco.override.Window', {
	override: 'Ext.window.Window',
	onShowComplete: function(cb, scope) {
		Ext.Component.prototype.onShowComplete.call(this,cb,scope);
		if( this.query('button[hidden=false]').length > 0){
			if(this.query('button[hidden=false]')[0]) {
				var noneFocusEl = this.query('button[hidden=false]')[0];
				if(noneFocusEl.el.dom.querySelector(".x-etna-uploader-dataview-icon")){
					var nextEl = this.query('button[hidden=false]')[1];
					if(nextEl){
						nextEl.focus();
					}
				}
			} else{
				this.query('button[hidden=false]')[0].focus();
			}
		}
	}
});

//적절한 서식 레이블 제공 2021.02.24 임상근
// 2021.03.03 임상근 textarea 통합
// 2021.03.23 오현석과장 전달 소스 수정
Ext.override(Ext.form.TextField,  {
	onRender: function() {
		this.callParent();
		
		var titleText = this.config.tooltip;
		if(!titleText) {
			titleText = (this.fieldLabel) ? this.fieldLabel: '입력 필드';
		}
		if (this.xtype === 'combobox') {
			titleText += ' ALT + 방향키로 이동가능';
		}
		
		var targetFieldEl = (this.xtype === 'textareafield') ? this.el.query('textarea')[0] : this.el.query('input')[0];
		if(targetFieldEl) {
			targetFieldEl.setAttribute('title', titleText);
		}
		
		// trigger 타이틀 추가
		if(this.triggers && Object.keys(this.triggers).length > 0) {
			for(var triggerKey in this.triggers) {
				var triggerComp = this.triggers[triggerKey];
				var triggerTitle;
				switch (triggerComp.cls) {
				case 'trigger-search':
					triggerTitle = '검색 버튼';
					break;
				}
				
				if(triggerTitle) {
					var triggerDom = triggerComp.el.dom;
					triggerDom.setAttribute('title', titleText +'의 '+ triggerTitle);
					triggerDom.setAttribute('tabindex',0);
					triggerDom.addEventListener('keydown', function(event) {
						//메모리 유발 가능
						if(event.keyCode === 13) {
							triggerComp.handler(this, triggerComp, null);
						}
					}.bind(this));
				}
			}
		}
	}
});

//적절한 서식 레이블 제공 2021.02.25 임상근 - R&D
// TExtfield와 통합
/*Ext.override(Ext.form.field.TextArea, {
	onRender: function() {
		this.callParent();
		
		var titleText = this.config.tooltip;
		if(!titleText) {
			titleText = (this.fieldLabel) ? this.fieldLabel: '텍스트영역 필드';
		}
		this.el.query('textarea')[0].setAttribute('title', titleText);
	}
});*/

// 2021.02.25 임상근 적절한 서식 레이블 제공 - R&D
//2021.03.17 임상근 전문가 상세 보고서 30p, 31p, 33p.fieldcontainer에 적합한 title 넣을 것
Ext.override(Ext.form.FieldContainer, {
	onRender: function() {
		this.callParent();
		
		if(this.fieldLabel) {
			var target = ['textfield', 'combobox', 'textareafield', 'textarea'];
			var items = this.items.items;
			for (var i=0; i<items.length; i++) {
				var item = items[i];
				if(item && target.indexOf(item.xtype) !== -1) {
					var postfix = item.config.postfix; // item의 postfix
					item.config.tooltip = this.fieldLabel + (postfix ? ' ' + postfix : '');
				}
			}
		}
	}
});

// 2021.02.25 임상근적절한 서식 레이블 제공  - R&D
Ext.override(Ext.form.Panel, {
	onRender : function() {
		this.callParent();
		this._applyCollapseButtonAltText();
	},
	
	/*afterRender: function() {
		this.callParent();
		if(this.getEl() && this.getEl().dom.tabIndex === 0) {
			this.getEl().dom.tabIndex = -1;
		}
	},*/

	_applyCollapseButtonAltText : function() {
		if (this.config.collapsible) {
			var dockBtnImg = this.el.query('img.x-tool-collapse-top, img.x-tool-expand-bottom')[0];
			
			if (dockBtnImg) {
				var panelText = ((this.title) ? this.title : '') + ' 패널';
				var stateText = (!this.collapsed) ? ' 접기' : ' 펼치기';
				dockBtnImg.setAttribute('alt', panelText + '의 ' + stateText
						+ '버튼');
				
				// 타이틀 추가
				var parentNode = dockBtnImg.parentNode;
				parentNode.setAttribute('title', (this.title + (!this.collapsed ? ' 접기' : ' 펼치기')));
				parentNode.tabIndex = 0;
				
				//Keydown 이벤트 추가
				if(!parentNode.getAttribute('data-hasKeyDownEvent')){
                  parentNode.addEventListener('keydown', function(event) {
						if(event.keyCode === 13) {
							parentNode.setAttribute('data-hasKeyDownEvent', true);
							if(!this.collapsed) {
								this.collapse();
								return;
							}
							this.expand();
						}
					}.bind(this));	
              }
			}
		}
	},

	collapse : function(e, a) {
		this.callParent(e, a);
		this._applyCollapseButtonAltText();
	},

	expand : function(a) {
		this.callParent(a);
		this._applyCollapseButtonAltText();
	}
});

//2021.03.02 임상근 comboboxfield 리더기에서 못읽음 - R&D 반영(page 158,163)
//2021.03.21 방향키를 사용한 expand시 aria-activedescendant가 설정되지 않는 이슈에 대한 처리
Ext.override(Ext.form.field.ComboBox, {
	_setAriaLabel : function(text) {
		var inputEl = this.el.query('input')[0];
		if (text) {
			inputEl.setAttribute('aria-label', text);
		} else if (this.config.emptyText) {
			inputEl.setAttribute('aria-label', this.config.emptyText);
		} else {
			inputEl.removeAttribute('aria-label');
		}
	},
	
	onRender : function() {
		this.callParent();
		this._setAriaLabel(undefined);
	},
	
	applyTriggers: function(triggers) {
		var result = this.callParent(arguments);
		if (result.picker && result.picker.renderTpl && result.picker.renderTpl.length) {
			result.picker.renderTpl[0] = result.picker.renderTpl[0].replace('<div', '<a tabindex="0" title="풀 다운 메뉴 열기"');
			result.picker.renderTpl[3] = '</a>';
		}
		return result;
	},
	
	expand: function() {
		this.callParent(arguments);
		
		// 초기화 부분
		var listbox = this.getPicker();
		var comboboxInputEl = this.el.query('input')[0];
		comboboxInputEl.setAttribute('aria-owns', listbox.listEl.id);
		comboboxInputEl.setAttribute('aria-controls', listbox.listEl.id);
		comboboxInputEl.setAttribute('aria-expanded', 'true');
		comboboxInputEl.setAttribute('aria-activedescendant','');
		comboboxInputEl.setAttribute('aria-haspopup', 'true');
		listbox.el.query('ul')[0].setAttribute('role', 'listbox');
				
		var liEls = listbox.listEl.el.query('li');
		for (var i = 0; i < liEls.length; i++) {
			var liEl = liEls[i];
			liEl.setAttribute('id', listbox.id + '-item' + i);
		}
	},
	
	afterRender: function() {
		this.callParent(arguments);
		new Ext.util.KeyNav({
			target: this.triggers.picker.el,
			eventName: 'keyup',
			scope: this,
			enter: function() {
				this.onTriggerClick();
			}
		});
	},
	
	listConfig : {
		_setAriaLabel : function(text) {
			var comboboxComp = this.getBubbleParent();
			if (comboboxComp && ([ 'combobox', 'combo' ].indexOf(comboboxComp.xtype) !== -1)) {
				comboboxComp._setAriaLabel(text);
			}
		},

		listeners : {
			highlightitem : function(view, node, eOpts) {
				this._setAriaLabel(node.textContent);
				
				this.ownerCmp.el.query('input')[0].setAttribute('aria-activedescendant', node.id);
			},
			
			deactivate : function(view, eOpts) {
				this._setAriaLabel(undefined);
			}
		}
	}
});


//2021.03.02 pdf 57p 그리드 헤더의 컨텍스트 버튼에 text 추가 - R&D 반영
Ext.override(Ext.grid.column.Column, {
	onRender: function() {
		this.callParent();
		var headerTriggerEl = this.el.query('.x-column-header-trigger')[0];
		if(headerTriggerEl && this.text) {
			headerTriggerEl.setAttribute('title', this.text + '의 컨텍스트 버튼');
		}
		if (this.config.isCheckerHd) { 
		    this.el.query('span.x-column-header-text')[0].setAttribute('aria-label', '전체 선택'); 
		}
	}
});

// 2021.03.02 임상근 pdf 67 페이징 툴바에 초점 주기
Ext.override(Ext.toolbar.Paging, { 
	afterRender: function() {
		this.callParent();
		var parentComp = this.getBubbleParent();
		if (parentComp.xtype !== 'gridpanel') {
			return;
		}
		var items = this.items.items;
		for (var i = 0; i < items.length; i++) {
			var item = items[i];
			if (item.xtype === 'numberfield' && item.cls === 'x-tbar-page-number') {
				var inputEl = item.el.query('input')[0];
				if (inputEl) {
					var prefixText = parentComp.summaryText ? (parentComp.summaryText + ' ') : '';
					inputEl.setAttribute('title', prefixText + '그리드의 현재 페이지'); // 기존 text
				}
			}
		}
	} 
});

// 2021.03.02 임상근 - pdf 57 그리드의 헤더 컨텍스트 메뉴 버튼 아이콘에 title이나, aria-label 값 넣기 
//[0] 웹접근성 제거대상(1.체크박스 그리드의 속도 문제 있음) : 2021.03.02 임상근 - pdf 57 그리드의 헤더 컨텍스트 메뉴 버튼 아이콘에 title이나, aria-label 값 넣기
//2022.04.28 Hoon 웹접근성 관련 롤백 구간1
//Ext.override(Ext.selection.CheckboxModel, { 
//	_getTargetColumnComp: function(view, record) { 
//		var targetColumnComp; 
//		var gridComp =view.grid; // 그리드를 가져오는 부분
//		if(gridComp.ownerGrid) {
//			gridComp = gridComp.ownerGrid;
//		}
//		
//		if (gridComp) {
//			if (gridComp.config.keyCellField) { 
//				var columns = gridComp.columns;
//				for (var i = 0; i < columns.length; i++) { 
//					var column = columns[i]; 
//					if (column.dataIndex === gridComp.config.keyCellField) { 
//						targetColumnComp = column; 
//						break; 
//					} 
//				} 
//			} else { 
//				targetColumnComp = gridComp.columns[0]; 
//			} 
//		} 
//		
//		return targetColumnComp; 
//	}, 
//	
//	_getTextFormColumnAndRecord: function(columnComp, record) { 
//		if (!columnComp) { 
//			return '선택'; 
//		} 
//		
//		var text = record.data[columnComp.dataIndex]; 
//		if (columnComp.xtype === 'etnastorecolumn') { 
//			var storedItems = columnComp.store.data.items; 
//			for (var i = 0; i < storedItems.length; i++) { 
//				var item = storedItems[i].data; 
//				if (text === item.value) { 
//					text = item.text; 
//					break; 
//				} 
//			} 
//		} 
//		
//		return text; 
//	}, 
//	
//	renderer: function(value, metaData, record, rowIndex, colIndex, store, view) { 
//		var columnComp = this._getTargetColumnComp(view, record); 
//		var selectionText = this._getTextFormColumnAndRecord(columnComp, record); 
//		return '<div class="' + Ext.baseCSSPrefix + 'grid-row-checker" role="presentation" aria-label="' + selectionText + '">&#160;</div>'; 
//	},
//	
//	onHeaderClick: function(headerCt, header, e) { 
//		var me = this, 
//		store = me.store, 
//		isChecked, records, i, len, 
//		selections, selection; 
//		
//		if (me.showHeaderCheckbox !== false && header === me.column && me.mode !== 'SINGLE') { 
//			e.stopEvent(); 
//			isChecked = header.el.hasCls(Ext.baseCSSPrefix + 'grid-hd-checker-on'); 
//			
//			var spanEl = headerCt.el.query('.x-column-header-text')[0]; 
//			if (isChecked) { 
//				records = []; 
//				selections = this.getSelection(); 
//				for (i = 0, len = selections.length; i < len; ++i) { 
//					selection = selections[i]; 
//					if (store.indexOf(selection) > -1) { 
//						records.push(selection); 
//					} 
//				} 
//				
//				if (records.length > 0) { 
//					me.deselect(records); 
//				} 
//				spanEl.setAttribute('aria-label', '전체 선택'); 
//			} else { 
//				me.selectAll(); 
//				spanEl.setAttribute('aria-label', '전체 선택 체크됨'); 
//			} 
//		} 
//	}, 
//	
//	// model의 코드를 가져와서 수정함 
//	doSelect: function(records, keepExisting, suppressEvent) { 
//		var me = this, record; 
//		
//		if (me.locked || records == null) { 
//			return; 
//		} 
//		
//		if (typeof records === "number") { 
//			record = me.store.getAt(records); 
//			if (!record) { 
//				return; 
//			} 
//			
//			records = [record]; 
//		} 
//		
//		if (me.selectionMode === "SINGLE") { 
//			if (records.isModel) { 
//				records = [records]; 
//			} 
//			
//			if (records.length) { 
//				var record = records[0]; 
//				me.doSingleSelect(record, suppressEvent); 
//				// 추가 항목 
//				this._setCheckboxAriaLabel(record, true); 
//			} 
//		} else { 
//			me.doMultiSelect(records, keepExisting, suppressEvent); 
//			// 추가 항목 
//			this._setCheckboxAriaLabel(records, true); 
//		} 
//	}, 
//	
//	// model의 코드를 가져와서 수정함 
//	doDeselect: function(records, suppressEvent) { 
//		var me = this, 
//			selected = me.selected, 
//			i = 0, 
//			len, record, 
//			attempted = 0, 
//			accepted = 0, 
//			commit;
//	        
//		if (me.locked || !me.store) { 
//			return false; 
//		} 
//		
//		if (typeof records === "number") { 
//			record = me.store.getAt(records); 
//			if (!record) { 
//				return false; 
//			} 
//			records = [record]; 
//		} else if (!Ext.isArray(records)) { 
//			records = [records]; 
//		} 
//		
//		commit = function() { 
//			++accepted; 
//			if (!suppressEvent) { 
//				selected.remove(record); 
//			} 
//			if (record === me.selectionStart) { 
//				me.selectionStart = null; 
//			} 
//		}; 
//		
//		len = records.length; 
//		me.suspendChanges(); 
//		for (; i < len; i++) { 
//			record = records[i]; 
//			if (me.isSelected(record)) { 
//				if (me.lastSelected === record) { 
//					me.lastSelected = selected.last(); 
//				} 
//				++attempted; 
//				// 추가 항목 
//				this._setCheckboxAriaLabel(record, false); 
//				me.onSelectChange(record, false, suppressEvent, commit); 
//				if (me.isDestroyed) { 
//					return false; 
//				} 
//			} 
//		} 
//		me.resumeChanges(); 
//		
//		if (suppressEvent) { 
//			selected.remove(records); 
//		} 
//		
//		me.maybeFireSelectionChange(accepted > 0 && !suppressEvent); 
//		return accepted === attempted; 
//	}, 
//	
//	_setCheckboxAriaLabel: function(record, doSelect) { 
//		var comp = this.column.getView().getRowByRecord(record); 
//		if (comp) { 
//			var checkEl = comp.querySelector('.x-grid-row-checker'); 
//			if( checkEl){
//				var text = checkEl.getAttribute('aria-label');
//				text = text ? text.replace(' 체크됨', '') : '항목';
//				
//				if(doSelect) text += ' 체크됨';
//	//	    text = doSelect ? (text + ' 체크됨') : text.replace(' 체크됨', ''); 
//				checkEl.setAttribute('aria-label', text);
//			}
//		} 
//	} 
//});
//웹접근성 관련 롤백 구간1 끝
// 2021.03.02 임상근 - pdf 72p 액션 컬럼 엔터키 동작
Ext.override(Ext.grid.column.Action, { 
	  constructor : function(config){ 
		  	config.enableKeyEvents = true; 
		  	this.callParent(arguments); 
	    
		  	this.addListener('keydown', this._keyDownEvent); 
	  }, 
	  _keyDownEvent: function(view, td, rowIndex, colIndex, e, record, tr, eOpts) { 
	   if (e.keyCode === 13) { 
		   if(this.handler) {
			   this.handler(view, rowIndex, colIndex, this, e, record, tr);
		   } else {
			   this.onHandler(view, rowIndex, colIndex, this, e, record, tr);
		   }
	     
	   } 
	  } 
}); 

// 2021.03.02 임상근  - pdf 92p 새창으로 이동하는 버튼에 타이틀 달기 linkNewWindow 속성이 있어야한다.
Ext.override(Ext.button.Button, { 
	  onRender: function() { 
	   this.callParent(arguments); 
	   if (this.linkNewWindow && (this.el.dom.tagName === 'A')) { 
	    this.el.dom.setAttribute('title', '새 창으로 이동'); 
	   } 
} 
}); 


// 2021.03.02 임상근 -pdf 92p 새창을 띄우는 버튼, 그리드 컬럼에 새창 띄움이라는 title 추가 할 것 
Ext.override(Ext.view.Table, { 
	  cellTpl: [ 
	         '<td class="{tdCls}" {tdAttr} {[Ext.aria ? "id=\\"" + Ext.id() + "\\"" : ""]} style="width:{column.cellWidth}px;<tpl if="tdStyle">{tdStyle}</tpl>" tabindex="-1" {ariaCellAttr} data-columnid="{[values.column.getItemId()]}">', 
	             '<div {unselectableAttr} class="' + Ext.baseCSSPrefix + 'grid-cell-inner {innerCls}" ', 
	                 'style="text-align:{align};<tpl if="style">{style}</tpl>" {ariaCellInnerAttr} <tpl if="column.linkNewWindow">title="새 창으로 이동"</tpl> >{value}</div>', 
	         '</td>', { 
           priority: 0 
       } 
   ] 
});


Ext.override(Etna.grid.column.Status, {
	defaultRenderer: function(a, b, c, d) {
		//console.log("ehllo!!!");
	}
});

//2021.03.02 임상근 - 그리드 내 이미지에 alt 달기
Ext.override(Ext.grid.column.Check , { 
	// checkbox 데이터 모델과 중복됨 
	_getTextFormColumnAndRecord: function(columnComp, record) { 
		if (!columnComp) { 
			return '선택'; 
		} 
		
		var text = record.data[columnComp.dataIndex]; 
		if (columnComp.xtype === 'etnastorecolumn') { 
			var storedItems = columnComp.store.data.items; 
			for (var i = 0; i < storedItems.length; i++) { 
				var item = storedItems[i].data; 
				if (text === item.value) { 
					text = item.text; 
					break; 
				} 
			} 
		} 
		return text; 
	}, 
	
	_getAltTextFromColumn: function(record) { 
		var keyCellField = this.config.keyCellField 
		var gridColumns = this.getView().grid.columns; 
		var targetColumn; 
		if (keyCellField) { 
			for (var i = 0; i < gridColumns.length; i++) { 
				var column = gridColumns[i]; 
				if (column.dataIndex === keyCellField) { 
					targetColumn = gridColumns[i]; 
					break; 
				} 
			} 
		} else { 
			for (var i = 0; i < gridColumns.length; i++) { 
				var column = gridColumns[i]; 
				if (column !== this&& column.xtype !== 'etnastatuscolumn') { 
					targetColumn = gridColumns[i]; 
					break; 
				} 
			} 
		} 
		return this._getTextFormColumnAndRecord(targetColumn, record); 
	}, 
	
	defaultRenderer : function(value, cellValues) { 
		var cssPrefix = Ext.baseCSSPrefix, 
			cls = cssPrefix + 'grid-checkcolumn'; 
			
		if (this.disabled) { 
			cellValues.tdCls += ' ' + this.disabledCls; 
		} 
		
		if (value) { 
			cls += ' ' + cssPrefix + 'grid-checkcolumn-checked'; 
		}
		//var altText = this._getAltTextFromColumn(cellValues.record);
		//checkcolumn의 경우 헤더 텍스트를 넣기로함
		//추가변경예정 2021.06.04 임시조치_홍영동
		//2022.03.21 Hoon 정상동작하도록 수
		var altText;
		if(cellValues && cellValues.column && cellValues.column.config && cellValues.column.config.text) {
			if (value) {
				altText = cellValues.column.config.text + ' 선택됨';
			}else {
				altText = cellValues.column.config.text;
			}
		} else {
			if (value) { 
				altText = "체크박스 선택됨";
			} else {
				altText = "체크박스";
			}
		}
		
		return '<img class="' + cls + '" src="' + Ext.BLANK_IMAGE_URL + '" alt="' + altText + '"/>';
	} 
}); 

//2021.03.02 임상근 - pdf 121p 팝업 닫힌 후에 기존 포커스로 돌아오도록 할 것 
Ext.define('Etna.override.window.MessageBox', {
	override: 'Ext.window.MessageBox', 	
	alert : function(msg, fn, scope) {
		this.prevActiveEl = document.activeElement; // 이전 포커스 기억
		this.callParent(arguments);
		this.a11yTreatFocus(); 	
	}, 	
	confirm : function(msg, fn, scope) {
		this.prevActiveEl = document.activeElement; // 이전 포커스 기억
		this.callParent(arguments); 		
		this.a11yTreatFocus(); 	
	}, 	
	error : function(msg, fn, scope) {
		this.prevActiveEl = document.activeElement; // 이전 포커스 기억
		this.callParent(arguments); 		
		this.a11yTreatFocus(); 	
	}, 	
	warn : function(msg, fn, scope) {
		this.prevActiveEl = document.activeElement; // 이전 포커스 기억
		this.callParent(arguments); 		
		this.a11yTreatFocus(); 	
	}, 	
	a11yTreatFocus: function(){ 		
		var closeEl = this.header.el.dom.querySelector("img.x-tool-close");
		closeEl.setAttribute("tabindex", "0"); // 포커스 가능하도록
		closeEl.focus(); // 닫기 버튼 강제 포커스 이동
		
		/*if(!closeEl.onkeyup) {
			closeEl.onkeyup = function(e) {
				if(*//**Enter*//* e.keyCode === 13) {
					this.close();
				}
			}.bind(this);
		}*/

		closeEl.addEventListener('keydown', function(event){
	         if(event.keyCode === 13) {
	         this.close();
	         }
	        }.bind(this));

	},
	hide: function() {
		this.callParent();
		this.prevActiveEl && this.prevActiveEl.focus();
	}
}); 

//2021.03.02 임상근 - pdf 21p : 팝업에서 버튼 포커스가 확실하게 나와있지 않음 
Ext.define('Cmmn_Sp_Popup.override.view.join.popup.IDDuplicateCheck', { 	
	override: 'Cmmn_Sp_Popup.view.join.popup.IDDuplicateCheck', 	
	show: function(animateTarget, cb, scope) { 		
		this.prevActiveEl = document.activeElement; // 이전 포커스 기억 		
		this.callParent(arguments); 	
	}, 	
	close: function() { 		
		this.prevActiveEl.focus(); // 이전 포커스로 이동 		
		this.callParent(arguments); 	
	} 
});

//2021.03.04 임상근 - LEFT 메뉴, TOP 메뉴 탭이동 소스 반영
//2021.03.23 - 2021.03.18 전달내용과 겹치는 관계로 주석처리함.
/*Ext.define('Mdi.view.override2.mdi.LeftViewController', { 	
	prevFocusOutElmentSelector: '.mdi-left-menu-header-left', 	
	nextFocusOutElmentSelector: '.x-tab-active', 	
	override: 'Mdi.view.mdi.LeftViewController', 	
	setMenu: function(menuData) { 		
		this.callParent(arguments);  		
		this.a11yInit(); 	
	}, 	
	a11yInit: function(){ 		
		this.treeContainer = this.view.el.dom.querySelector(".x-grid-item-container"); 		
		if(this.treeContainer == null){ 			
			setTimeout(function(){ 				
				this.a11yInit(); 			
			}.bind(this), 1000); 			
			return; 		
		} 		 		
		*//** Expand SubMenu *//* 		
		if(!this.treeContainer.onkeyup){ 			
			this.treeContainer.onkeyup = function(e){ 				
				e.preventDefault(); 				
				e.stopPropagation(); 				
				var record = this.view.selModel.navigationModel.position.record; 				
				if(*//** TabKey *//*e.keyCode == 9  && e.shiftKey == false){ 					
					if(record && record.data.children && record.data.children.length > 0 && record.expand){ 						
						record.expand();
						// alt 초기화 방지를 위해서 호출
						this.adjustWidth();
					}
				}else if(*//** TabKey *//*e.keyCode == 9  && e.shiftKey == true){ 					
					if(record && record.data.children && record.data.children.length > 0 && record.expand){ 						
						record.expand(); 	
						// alt 초기화 방지를 위해서 호출
						this.adjustWidth();
					} 				
				}
			}.bind(this); 		
		} 		 		
		*//** Move Next Menu *//* 		
		if(!this.treeContainer.onkeydown){ 			
			this.treeContainer.onkeydown = function(e){ 	    	
				if(*//** TabKey *//*e.keyCode == 9  && e.shiftKey == false){ 	    		
					this.a11yTabkeyDownHandler(e); 	    	
				} else if(e.keyCode == 9 && e.shiftKey == true){ 	    		
					this.a11yUnTabkeyDownHandler(e); 	    	
				} 	    
			}.bind(this); 		
		} 	
	}, 	
	a11yTabkeyDownHandler: function(e){ 		
		e.preventDefault(); 		
		e.stopPropagation(); 		 		
		*//** 마지막 로우(포커스가 밖으로 나가야 됨) *//* 		
		if(this.view.selModel.store.data.items.length-1 == this.view.selModel.navigationModel.position.rowIdx){ 			
			var next = document.querySelector(this.nextFocusOutElmentSelector); 			
			next.focus(); 		
		} else{ 			
			var navModel = this.view.selModel.navigationModel; 			
			var idx = navModel.position.rowIdx+1; 			
			this.view.selModel.select(idx); 			
			this.view.selModel.navigationModel.position.rowIdx = idx; 			
			//this.view.selModel.navigationModel.position.colIdx = 0; 			
			//this.view.selModel.navigationModel.position.column = navModel.column; 			
			//this.view.selModel.navigationModel.position.record = this.view.selModel.store.data.items[idx]; 			
			this.view.selModel.navigationModel.setPosition(this.view.selModel.navigationModel.position); 		
		} 	
	}, 	
	a11yUnTabkeyDownHandler: function(e){ 		
		e.preventDefault(); 		
		e.stopPropagation(); 		 		
		*//** 첫번째 로우(포커스가 밖으로 나가야 됨) *//* 		
		if(this.view.selModel.navigationModel.position.rowIdx == 0){ 			
			var prev = document.querySelector(this.prevFocusOutElmentSelector); 			
			prev.focus(); 		
		}else{ 			
			this.view.selModel.select(this.view.selModel.navigationModel.position.rowIdx-1); 		
		} 	
	} 
});  */

Ext.define('Etna.override.toolbar.Toolbar', { 	
	override: 'Ext.toolbar.Toolbar', 	
	afterFocusableChildFocus: function(child){ 		
		if(this.alwaysFirst && !this.initCompleted){ 			
			this.callParent(arguments);  			
			this.initCompleted = true; 			
			this.alwaysFocusedChild = this.lastFocusedChild; 		
		}else{ 			
			this.lastFocusedChild = this.alwaysFocusedChild; 		
		} 	
	} 
});  

Ext.define('Mdi.a11y.view.mdi.TopViewController', { 	
	override: 'Mdi.view.mdi.TopViewController', 	
	count: 0, 	
	TopMenuManager:{ 		
		scope:{}, 		
		topMenu:{}, 		
		focusOutElment:{ 			
			previous:function(){
				return document.querySelector("a[componentid=kepco-mdi-logo-button]");
				//return MdiManager.mdiTab.up().lookupReference('mdiTop').items.items[0].query('button[hidden=false]:last')[0].el.dom;			
			}, 			
			next:function(){ 				
				var iframes = document.querySelectorAll("iframe"); 	
				for(var i=0; i<iframes.length; i++) {
				//debugger;
					if(iframes[i].id.indexOf("mdiiframe")>=0){ 						
						return iframes[i].contentWindow.document.querySelector("a.slidesjs-previous.slidesjs-navigation>img"); 					
					} 				
				} 				
            
				if(document.querySelector('.mdi-homebar a')){ 					
					//debugger; 
					return document.querySelector('.mdi-homebar a'); 				
				} 				
            
				return null; 			
			} 		
		}, 		
		current: function(){ 			
            var me = this.scope; 			
            return me.menuBar.el.dom.querySelector(/**.x-btn-pressed*/".x-btn-menu-active"); 		
		}, 		
		previous: function(){ 			
            var compId = this.current().getAttribute("componentid"); 			
            var previousSibling = this.topMenu[compId].button.el.dom.previousElementSibling;
            if(previousSibling && previousSibling.text == '통합검색') {
            	previousSibling = previousSibling.previousSibling;
            }
            if(previousSibling){ 				
				return this.topMenu[previousSibling.getAttribute("componentid")]; 			
			} else{ 				
				return null; 			
			} 		
		}, 		
		next: function(){ 			
            var compId = this.current().getAttribute("componentid");
            var nextSibling = this.topMenu[compId].button.el.dom.nextElementSibling;
            if(nextSibling && nextSibling.text == '통합검색') {
            	nextSibling = nextSibling.nextElementSibling;
            }
            if(nextSibling){ 				
				return this.topMenu[nextSibling.getAttribute("componentid")]; 			
			} else{ 				
				return null; 			
			} 		
		} 	
	},   
	initMenuBar: function(menus) {   	
        this.callParent(arguments);   	
        this.a11yInit();   
	},      
	/** 탭키 이동을 위한 로직 시작 */   
	a11yInit: function(){   	
        if(!this.menuBar){     	
            this.menuBar = this.lookupReference("menuBar");     	
            this.menuBar.alwaysFirst = true;     
		}     
        this.createTopManager();     
        this.topMenuBarListener();   
	},      
	/** Top메뉴의 버튼을 관리하는 TopManager 생성 */   
	createTopManager: function(){   	
        var buttons = menuBar.query("button");  		
        this.TopMenuManager.scope = this;     
		for(var i=0; i<buttons.length; i++){
            if(!buttons[i].hidden){ 
				this.TopMenuManager.topMenu[buttons[i].el.dom.getAttribute("componentid")] = { 
					button : buttons[i], 
					menuid : buttons[i].config.menuId 
				} 
			} 
		} 
	}, 
	/** Left메뉴 여부 */ 
	hasLeftMenu: function(){ 
        var mdi = this.view.up(), 
		mdiLeft = mdi.query("mdileft"); /** MDILeft 여부 */ 
        if(mdiLeft && mdiLeft.length > 0){ /** 숨김여부 */ 
			if(mdiLeft[0].hidden){ 
				return false; 
			} else{ /** Expand/Collapse 여부 */ 
				if(!mdiLeft[0].collapsed){ 
					return true; 
				} 
				return false; 
			} 
		} else{ 
            return false; 
		} 
	}, 
	/** Top메뉴 리스너 등록 */ 
	topMenuBarListener: function(){ 
        this.topMenuMoveListener(); 
        this.topMenuMoveWithSubmenuListener(); 
	}, 
	/** Left메뉴가 존재하면, 좌/우로만 이동 */ 
	topMenuMoveListener: function(){ 
        this.menuBar.el.dom.onkeydown = function(e){ 
			if(this.hasLeftMenu()){ 
				if(/** TabKey */e.keyCode == 9){ 
					var topMenuKeyList = Object.keys(this.TopMenuManager.topMenu); 
					var currentMenuBtnEl = this.menuBar.el.dom.querySelector(".x-btn-focus") 
					var compId = currentMenuBtnEl.getAttribute("componentid"); 
					/** 네이티브 이벤트 제어 */ 
					e.preventDefault(); 
					e.stopPropagation(); 
					if(e.shiftKey == false){ 
					/** 정방향 */ /** 다음 메뉴 선정 */ 
						for(var i=0,topMenuKey,nextTopMenu; i< topMenuKeyList.length; i++){
							topMenuKey = topMenuKeyList[i];
							if(topMenuKey == compId){ 
								var index = i+1; 
								if(index < topMenuKeyList.length){ 
									nextTopMenu = this.TopMenuManager.topMenu[topMenuKeyList[index]]; 
								} else{ 
									/** Top메뉴 포커스에서 벗어남 */ 
									nextTopMenu = this.TopMenuManager.focusOutElment.next(); 
								} 
								break; 
							} 
						} 
					} else{ 
					/** 역방향 */ /** 이전 메뉴 선정 */ 
						for( var i=0,topMenuKey,nextTopMenu; i<= topMenuKeyList.length; i++){ 
							topMenuKey = topMenuKeyList[i];
							if(topMenuKey == compId){ 
								var index = i-1; 
								if(index >= 0){ 
									nextTopMenu = this.TopMenuManager.topMenu[topMenuKeyList[index]]; 
								} else{ 
									/** Top메뉴 포커스에서 벗어남 */ 
									nextTopMenu = this.TopMenuManager.focusOutElment.previous(); 
								} 
								break; 
							} 
						} 
					} 
					/** 이전 메뉴 포커스 CSS 제거 */ 
					var pressedTopBtn = this.menuBar.el.dom.querySelector(".x-btn-pressed"); 
					if(pressedTopBtn){ 
						pressedTopBtn.classList.remove("x-btn-pressed"); 
					} 
					/** 다음 메뉴 포커스 */ 
					if(nextTopMenu){ 
						if(nextTopMenu.button){ 
							nextTopMenu.button.setPressed(); 
							nextTopMenu.button.focus(); 
						} else{ 
						/** Focus Out */ 
							nextTopMenu.focus(); 
						} 
					} 
				} 
			} 
		}.bind(this); 
	}, 
	/** Left메뉴가 없으면, 서브메뉴를 활용한 상/하/좌/우/ 이동 */ 
	topMenuMoveWithSubmenuListener: function(){ 
		this.menuBar.el.dom.onkeyup = function(e){ 
			if(!this.hasLeftMenu()){ 
				if(/** TabKey */e.keyCode == 9 && e.shiftKey == false){ 
					this.a11yTabkeyUpHandler(e.target, e); 
				} else if(e.keyCode == 9 && e.shiftKey == true){ 
					//this.a11yUnTabkeyUpHandler(e.target, e);  
					this.a11yTabkeyUpHandler(e.target, e); 
				} 
			} 
		}.bind(this); 
	}, 
	/** 서브메뉴 박스내의 아이템 목록 핸들링 */ 
	a11yTabkeySubMenuBoxLastItemHandler: function(e, reverse){ 
		//debugger; 
		if(!reverse){ 
			var currentMenu = this.a11yGetSubMenu(e.target); 
			var nextMenu = currentMenu.up().ownerCmp.next(); currentMenu.deactivate(); 
			// 비활성화 
			currentMenu.up().hide(); 
			// 서브메뉴 숨김  
			if(nextMenu){ 
				//debugger; 
				nextMenu.up().setActiveItem(nextMenu); nextMenu.focus(); 
			} else{ 
				this.a11yTabkeyMenuBoxLastItemHandler(e); 
			} 
			//nextTopMenu = this.TopMenuManager.next();  
		} else{ /** 역방향 */ 
			var currentMenu = this.a11yGetSubMenu(e.target); 
			var prevMenu = currentMenu.up().ownerCmp.prev(); currentMenu.deactivate(); 
			// 비활성화 
			currentMenu.up().hide(); 
			// 서브메뉴 숨김  
			if(prevMenu){ 
				//debugger; 
				prevMenu.up().setActiveItem(prevMenu); prevMenu.focus(); 
			} else{ 
				this.a11yTabkeyMenuBoxLastItemHandler(e, reverse); 
			} 
		} 
	}, 
	/** 메뉴 박스내의 아이템 목록 핸들링 */ 
	a11yTabkeyMenuBoxLastItemHandler: function(e, reverse){ 
		/** 현재 포커스중인 상위 탑메뉴의 componentid를 가져옴 */ 
		if(this.menuBar.el.dom.querySelector(/**.x-btn-pressed*/".x-btn-menu-active")){ 
			/** 네이티브한 탭키 포커스 중지 */ 
			e.preventDefault(); e.stopPropagation(); 
			var compId = this.menuBar.el.dom.querySelector(/**.x-btn-pressed*/".x-btn-menu-active").getAttribute("componentid"); 
			/** componentid를 통해, 메뉴 객체 가져옴 */ 
			var menu = this.TopMenuManager.topMenu[compId]; /** 탑메뉴 중 다음 순번의 메뉴객체 가져옴 */ 
			var nextTopMenu; 
			if(!reverse){ 
			   nextTopMenu = this.TopMenuManager.next(); 
			} else{ 
				/** 역방향 */ 
				nextTopMenu = this.TopMenuManager.previous(); 
			} 
			if(nextTopMenu){ /** 메뉴박스 오픈 */ 
				this.a11yShowMenu(nextTopMenu.button); 
			} else{ 
				this.closingMenu = true; 
				//menu.button.hideMenu(); 
				var next = null; 
				if(reverse){ 
					next = this.TopMenuManager.focusOutElment.previous(); 
				} else{ 
					next = this.TopMenuManager.focusOutElment.next(); 
				} 
				if(next){ 
					setTimeout(function(){ 
						if(this.closingMenu){ 
							this.closingMenu = false; 
							next.focus(); 
						} 
					}.bind(this), 200); 
				} else{ 
					setTimeout(function(){ 
						if(this.closingMenu){ 
							this.closingMenu = false; 
							document.body.focus(); 
						} 
					}, 200); 
				} 
			} 
			setTimeout(function(){ 
				/** 이전 메뉴박스 닫기 */ 
				menu.button.hideMenu(); 
			}, 100); 
		} else{ 
			debugger; 
		} 
	}, 
	a11yGetSubMenu: function(el){ 
		var compId = el.getAttribute("componentid"); 
		if(Ext.isEmpty(compId)){ 
			var activeItemMenu = el.querySelector(".x-menu-item-active"); 
			if(activeItemMenu){ 
				compId = activeItemMenu.firstElementChild.getAttribute("componentid"); 
			} 
		} 
		return this.menuBar.query("menuitem[id="+compId+ "]")[0]; 
	}, 
	/** 메뉴박스에 Tab키 이벤트 발생 */ 
	a11yTabkeyMenuItemBoxHandler: function(e){ 
		var currentElement = e.target; 
		if(!e.target.classList.contains("x-menu-item-active")){ 
			var activeMenuItem = e.target.parentElement.parentElement.querySelector(".x-menu-item-active"); 
			if(activeMenuItem){ 
				currentElement = activeMenuItem.firstElementChild; 
			} 
		} 
		if(!currentElement.querySelector("div.x-menu-item-arrow") && e.target.querySelector(".x-menu-item-active")){ 
			currentElement = e.target; 
		} 
		/** SubMenu가 있으면 */ 
		if(currentElement.querySelector("div.x-menu-item-arrow")){ 
			var subMenu = this.a11yGetSubMenu(currentElement); 
			if(subMenu && subMenu.menu){ 
				e.preventDefault(); 
				e.stopPropagation(); 
				subMenu.doExpandMenu(); 
				setTimeout(function(){ 
				/** 오픈된 하위메뉴박스에 탭키 이벤트 등록 */ 
					this.a11yAddTabKeyUpOnMenuItemBox(); 
				}.bind(this), 10); 
			} 
		} else{ 
			/** 메뉴박스 내의 다음 엘리먼트가 없으면, 마지막을 의미.(상단의 다음 탑메뉴로 이동해야 할 이벤트를 등록해야함) */ 
			var prevEl = currentElement.parentElement.previousElementSibling; 
			var nextEl = currentElement.parentElement.nextElementSibling; 
			/** prevEl: null -> 첫번째 메뉴, 
				nextEl: null 마지막 메뉴 */ 
			if(prevEl == null || nextEl == null){ 
				if(!e.target.onkeydown){ 
				//debugger; 
				/** 메뉴박스 내의 마지막 아이템인 경우, 다음 탑메뉴로 이동할 수 있도록 키다운 이벤트 등록 */ 
					var menuItemCandidate = currentElement.getAttribute("componentid"); 
					/** 메뉴박스 아이템 여부 확인 */ 
					if(menuItemCandidate && menuItemCandidate.indexOf("menuitem")>=0){ 
						currentElement.onkeydown = function(e){ 
							if(/** TabKey */e.keyCode == 9 && e.shiftKey == false && nextEl == null){ 
								if(this.a11yGetDepth(e.target.getAttribute("componentid"))>2){ 
									this.a11yTabkeySubMenuBoxLastItemHandler(e); 
								} else{ 
									this.a11yTabkeyMenuBoxLastItemHandler(e); 
								} 
							} else if(/** TabKey */e.keyCode == 9 && e.shiftKey == true && prevEl == null){ 
								if(this.a11yGetDepth(e.target.getAttribute("componentid"))>2){ 
									this.a11yTabkeySubMenuBoxLastItemHandler(e, true); 
								} else{ 
									this.a11yTabkeyMenuBoxLastItemHandler(e, true); 
								} 
							} 
						}.bind(this); 
					} 
				} 
			} 
		} 
	}, 
	/** 메뉴박스 이벤트 등록 */ 
	a11yAddTabKeyUpOnMenuItemBox: function(){ 
		/** document.activeElement : 오픈된 메뉴박스 엘리먼트를 기대함 */ 
		if(!document.activeElement.onkeyup){ 
			/** 메뉴박스에 탭키 이벤트 등록 */ 
			document.activeElement.onkeyup = function(e){ 
				//debugger; 
				if(/** TabKey */e.keyCode == 9){ 
					// 1. Clear Active 
		  
					// 2.1. Active Class TopMenu  
					// 2. Move Next Focus  
					// 2.2. ShowMenu  
					this.a11yTabkeyMenuItemBoxHandler(e); 
				} 
				// this.menuBar.el.dom.querySelector(".x-btn-pressed.x-btn-menu-active")  
			}.bind(this); 
		} 
	}, 
	/** 상단 탑메뉴의 탭키 이벤트 핸들러 */ 
	a11yTabkeyUpHandler: function(menuEl, e){ 
		var compId = menuEl.getAttribute("componentid"); 
		if(Ext.isEmpty(compId)){ 
			//debugger; 
		} else{ 
			var menu = this.TopMenuManager.topMenu[compId]; 
			this.a11yShowMenu(menu.button); 
		} 
	}, 
	/** 상단 Top메뉴에서 메뉴박스를 오픈하고, 생성된 메뉴박스에 탭키 이벤트 등록 */ 
	a11yShowMenu: function(topBtn){ /** 상단 Top메뉴의 최상위에서 하위 메뉴 오픈 */ 
		if(this.showingMenu || this.closingMenu){ 
			return; 
		} 
		this.showingMenu = true; 
		topBtn.showMenu(); 
		setTimeout(function(){ /** 오픈된 하위메뉴박스에 탭키 이벤트 등록 */this.a11yAddTabKeyUpOnMenuItemBox(); 
			this.showingMenu = false; 
			var pressedTopBtn = this.menuBar.el.dom.querySelector(".x-btn-pressed"); 
			if(pressedTopBtn){ 
				pressedTopBtn.classList.remove("x-btn-pressed"); 
			} 
		}.bind(this), 10); 
	}, 
	a11yGetDepth: function(compId){ 
		return this.menuBar.query("menuitem[id="+compId+ "]")[0].menuData.data.depth; 
	}, 
	a11yUnTabkeyUpHandler: function(menuEl){ 
		//debugger; 
	} 
}); 


// 2021.03.05 임상근 첨부파일 통합 소스
//추가 반영소스 첨부
//[1] 웹접근성 제거대상(첨부파일 많을수록 느려짐) : 2021.03.05 임상근 첨부파일 통합 소스 [TECHSUPP-2133]
/** 첨부파일 웹접근성 */
//2022.04.28 Hoon 웹접근성 관련 롤백 구간2
//Ext.define('Etna.override.a11y.upload.StoreBasedUploader', {
//	override: 'Etna.upload.StoreBasedUploader',
//	onPluploadInit: function(uploader, data){		
//		this.callParent(arguments);
//		
//		/** 첨부파일 웹접근성 로직 추가 */
//		this.a11yInit();
//	},
//	
//	/** 웹접근성 Initialize */
//	a11yInit: function(){
//		//console.log("a11yInit..");
//		//window.uploadDiv = this;
//		//window.upload = this;
//		this.a11yToolbarButtons();
//		/** 76, 102 첨부파일 컴포넌트 wrapper 영역에 포커스 안가도록 할 것 */
//		if(Ext.isIE11){
//			this.body.dom.nextElementSibling.disabled = true;
//		}else{
//			this.body.dom.nextElementSibling.setAttribute("tabindex", "-1");
//		}
//		
//		/** 키보드 이벤트 활성화 */
//		if(!this.container.dom.onkeyup){
//			this.container.dom.onkeyup = this.onKeyHandler.bind(this);
//		}		
//	},
//	
//	/** Column Header Focus : (에디팅 가능한 상태에서 모든 파일목록 삭제 후) 포커스 처리 */
//	setHeaderFocus: function(){
//		var header = this.down("headercontainer")
//		var view = this.getView();
//		if(view.type == "dataview"){
//			this.down("container>button").focus()
//		}else{
//			header.columnManager.columns[0].focus();
//		}
//	},
//	
//	/** 체크박스 컬럼헤더 엔터 처리 */
//	a11yCheckColumnHeader: function(e){
//		//if(/** Enter */ e.keyCode == 13 && !this.checkedColumn){
//			var header = this.down("headercontainer");
//			var columns = header.columnManager.columns;
//			for(var i=0; columns && i<columns.length; i++){
//				if(columns[i].el.dom.innerText.indexOf("삭제") >= 0){
//					this.checkedColumn = columns[i];
//					this.checkedColumn.el.on({ keydown : function(e){
//						if(e.keyCode === 13) {
//							this.selectAllFiles();
//						}
//					}.bind(this) })
//					return;
//				}
//			}
//		//}
//	},
//	
//	a11yToolbarButtons: function(){
//		/** 76, 102 첨부파일 컴포넌트 wrapper 영역에 포커스 안가도록 할 것 */
//		var fileInput = this.container.down("input");
//		if(fileInput) {
//			if(Ext.isEmpty(fileInput.dom.getAttribute("title"))){
//				fileInput.dom.setAttribute("title", "파일첨부");
//			}
//			// 83. 첨부파일 컴포넌트의 파일 첨부 버튼에 input에 title 필요(포커스를 A태그로 가도록 함)
//			fileInput.dom.setAttribute("tabindex", "-1");
//		}
//		if(this.body){
//			this.body.dom.previousElementSibling.setAttribute("tabindex", "-1");
//		}
//		
//		/** 툴바 버튼 */
//		var btns = this.getTbar().query('button');
//		for(var i=0; i<btns.length; i++){	
//			/** 101. 첨부파일 버튼 키보드 제어 불가 */
//			if(btns[i].el.dom.display != "none"){
//				btns[i].el.dom.setAttribute("tabindex", "0");
//			}
//			if(!btns[i].text){
//				/** 78. 첨부파일 컴포넌트 버튼에 포커스 표시 안됨*/
//				if(btns[i].container.first() == btns[i].el){
//					/** Image View */
//					btns[i].el.dom.setAttribute("title", "Image View");
//				}else{
//					/** List View */
//					btns[i].el.dom.setAttribute("title", "List View");
//				}
//			}
//		}
//		// segmentedbutton의 toggle 이벤트 매핑
//		var segBtn = this.down('segmentedbutton');
//		var segItems = segBtn.items.items;
//		for(var i=0; i<segItems.length; i++) {
//			var item = segItems[i];
//			if(item.pressed) {
//				item.el.dom.setAttribute('title', item.el.dom.title + ' 선택됨');
//			}
//		}
//		segBtn.on("toggle", this.onSegToggle, this);
//	},
//	onSegToggle: function(target, button, isPressed, eOpts) {
//		var segItems = target.items.items;
//		for(var i=0; i<segItems.length; i++) {
//			var item = segItems[i];
//			item.el.dom.setAttribute('title', item.el.dom.title.replace(' 선택됨', ''));
//			if(item === button) {
//				item.el.dom.setAttribute('title', item.el.dom.title + ' 선택됨');
//			}
//		}
//	},
//	onKeyHandler: function(e){ 
//		if(/** Enter */ e.keyCode == 13){	
//			if(/** Check Column */e.target.querySelector(".x-grid-row-checker")){
//				this.onDeleteKeyHandler(e);
//			}else{
//				/** File Column */
//				this.onEnterKeyHandler(e.target);
//			}
//		}else if(/** tab */ e.shiftKey && e.keyCode == 9){
//			
//		}else if(e.keyCode == 46){
//				this.onDeleteKeyHandler(e);
//		}
//		this.a11yAccessContainer(e);
//		//this.prevTarget = e.target;
//		this.a11yCheckColumnHeader(e);
//		if(Ext.isIE11){
//			this.a11yColumnHeaderEnable(e);
//		}
//	},
//	a11yColumnHeaderEnable: function(e){
//		if(!this.headerEnable){
//			var header = this.down("headercontainer");
//			var columns = header.columnManager.columns;
//			for(var i=0; columns && i<columns.length; i++){
//				columns[i].el.dom.setAttribute("tabindex", "0");
//				this.headerEnable = true;
//			}
//		}
//	},
//	/** 이미지(데이터)뷰 인경우, Delete Key를 통해 제거 가능(단, 로컬파일만 가능)  */
//	onDeleteKeyHandler: function(e){
//		var el = e.target;
//		var dataviews = el.parentElement.querySelectorAll(".x-etna-dataview-item");
//		if(dataviews.length > 0){
//			/** Image(Data) View */
//			el = this.body.dom.querySelector(".x-view-item-focused");
//			for(var i=0; i<dataviews.length; i++){
//				if(el == dataviews[i]){
//					if(el.querySelector(".local")){
//						e.preventDefault();
//						e.stopPropagation();
//						
//						setTimeout(function(){
//							var view = this.getView();
//							var sm = view.getSelectionModel();
//							var record = sm.store.data.items[i] || sm.store.data.items[i-1];
//							sm.setLocked(false);
//							sm.select(record, true);
//							sm.setLocked(true);
//						}.bind(this), 10);
//						this.removeFile(this.getAttachedFiles()[i].id);
//						if(!this.files || this.files.length < 1){
//							this.setHeaderFocus()
//						}
//					}
//					return;
//				}
//			}	
//		}else{
//			/** List View */
//			var listview = this.body.dom.querySelectorAll(".x-grid-cell-row-checker");
//			for(var i=0; i<listview.length; i++){
//				if(el == listview[i]){
//					if(el.parentElement.querySelector(".x-etna-grid-uploader-status-local")){
//						e.preventDefault();
//						e.stopPropagation();
//						
//						/** NavigationModel을 사용한 포커스 이동 */
//						var panel = this.down("panel");
//						var selModel = panel.getSelectionModel();
//						selModel.select(i);
//						selModel.navigationModel.position.rowIdx = i;
//						selModel.navigationModel.position.colIdx = 0;
//						selModel.navigationModel.position.column = selModel.column;
//						selModel.navigationModel.position.record = selModel.store.data.items[i];
//						selModel.navigationModel.setPosition(selModel.navigationModel.position);
//					}
//					if(!this.files || this.files.length < 1){
//						this.setHeaderFocus();
//					}
//					return;
//				}
//			}
//			
//		}
//	},
//	onEnterKeyHandler: function(targetEl){
//		if(targetEl.querySelector("div.x-etna-grid-uploader-file-default")){
//			/** [Download File] 156. 파일에 포커스 맞춘 뒤 엔터 누르면 첨부파일 실행 */
//			this.a11yOnDownload(targetEl);
//		}else if(targetEl.querySelector("span.x-btn-inner")){
//			/** 툴바에 위치한 버튼들 실행 */
//			this.a11yOnClick(targetEl);
//		}else if(targetEl.querySelector("div.file-wrap")){
//			this.a11yOnDataviewDownload(targetEl);
//		}
//	},
//	a11yOnDownload: function(el){
//		if(Ext.isIE11){
//			var candidateEl = el.querySelector("div.x-etna-grid-uploader-file-default");
//			var fileEls = this.body.dom.querySelectorAll("div.x-etna-grid-uploader-file-default");
//			for(var i=0; i<fileEls.length; i++){
//				if(candidateEl == fileEls[i]){
//					this.download(this.getAttachedFiles()[i]);
//					return;
//				}
//			}
//		}else{
//			el.click();
//		}
//	},
//	a11yOnDataviewDownload: function(el){
//		var dataviews = el.parentElement.querySelectorAll(".x-etna-dataview-item");
//		for(var i=0; i<dataviews.length; i++){
//			if(el == dataviews[i]){
//				this.download(this.getAttachedFiles()[i]);
//				return;
//			}
//		}
//	},
//	a11yOnClick: function(el){
//		/** A태그인 경우, IE에서도 정상 동작 */
//		el.click();
//	},
//	/** 76, 102 첨부파일 컴포넌트 wrapper 영역에 포커스 안가도록 할 것 */
//	a11yAccessContainer: function(e){
//		var el = e.target;
//		/** Dynamic하게 동작. 내부에 파일리스트가 있으면, 포커스 가능해야 함 */
//		if(this.body.dom.querySelector(".x-grid-item-container > table")){
//			if(Ext.isIE11){
//				/** 03.08 : IE에서 tabindex가 없는 케이스가 존재하여, componentid로 변경 */
//				this.body.dom.querySelector("div[componentid].x-grid-view").setAttribute("tabindex", "0");
//				this.body.dom.querySelector("div[componentid].x-grid-view").disabled = false;
//			}else{
//				this.body.dom.querySelector("div[componentid].x-grid-view").setAttribute("tabindex", "0");
//			}
//			if(!this.getTbar().getComponent("closeButton").hidden && this.getTbar().getComponent("deleteButton").el.dom.tabIndex == -1){
//				this.getTbar().getComponent("deleteButton").el.dom.tabIndex = 0;
//			}
//		}else{
//			if(Ext.isIE11){
//				this.body.dom.querySelector("div[tabindex].x-grid-view").setAttribute("tabindex", "-1");
//				this.body.dom.querySelector("div[tabindex].x-grid-view").disabled = true;
//			}else{
//				this.body.dom.querySelector("div[tabindex].x-grid-view").setAttribute("tabindex", "-1"); // 불필요한 포커스
//			}
//		}	
//		
//		if(el && el.parentElement){
//			/** Image View Role : 방향키를 통한 이동이 가능하도록 Role 적용 */
//			var items = el.parentElement.querySelectorAll("div.x-etna-dataview-item:not([role])");
//			for(var i=0,itemEl; i<items.length;i++){
//				items[i].setAttribute("role", "menuitem");
//			}
//		}
//			
//		/** [IE11] Header 불필요한 포커스(헤더에서 빠져나가는 순간, tabindex가 0으로 바뀌어 setTimeout 사용 */
//		if(Ext.isIE11){
//			setTimeout(function(){
//				Etna.onDone(function(){
//					var view = this.getView();
//					
//					this.down("toolbar").el.dom.setAttribute("tabindex", "-1");
//					if(this.down("headercontainer")){
//						this.down("headercontainer").el.dom.setAttribute("tabindex", "-1");	
//					}
//					
//					/** 이미지뷰이고, 팝업창인 경우 */
//					if(this.getView().type == "dataview" && this.up().up().xtype == 'window'){
//						//console.log("el :: "+el.outerHTML);
//						var compId = el.getAttribute("componentId");
//						/** 탭키를 통한, 포커스 이동하지 않는 케이스 */
//						if(/** tab */e.keyCode == 9){
//							if(compId && compId.indexOf("etnadataviewuploader") >= 0){
//								var toolbar = this.getTbar();
//								var item = toolbar.el.dom.querySelector("a:not(.x-btn-disabled)");
//								item.focus();
//							}	
//						}
//					}
//				}.bind(this));
//			}.bind(this), 100);
//		}
//	}
//});
//웹접근성 관련 롤백 구간2 끝 
Ext.define('Etna.override.moveTab.toolbar.Toolbar', {
	override: 'Ext.toolbar.Toolbar',
	deactivateFocusable: function(child, /* optional */ newTabIndex) {
			
			if(this.allowMoveByTab()){
				child.setTabIndex(0);
			}else{
				this.callParent(arguments); 
			}
	},
	/** Toolbar내에 탭키를 이용한 이동을 사용하기 위한 조건 */
	allowMoveByTab: function(){
		/** 내부 사용자 제외 */
		if(Cmmn.User.data && Cmmn.User.data.userType === 'Internal'){
			return false;
		}
		
		/** 버튼만 */
		var buttons = this.query("button");
		if(buttons && buttons.length>0){
			return true;
		}else{
			return false;
		}
	},
	/** 간헐적 불필요한 컨테이너 포커스 진입 조치 */
	activateFocusableContainerEl: function(el) {
			/** AS-IS 소스 주석처리
      el = el || this.getFocusableContainerEl();
      el.set({ tabindex: this.activeChildTabIndex });
      */
  },
});

// 2021.03.03 임상근 - 회원가입 포커스
Ext.define('Cmmn_Sp_Popup.a11y.override.view.join.member.VendorChoice', { 	
	override: 'Cmmn_Sp_Popup.view.join.member.VendorChoice', 	
	initComponent: function(){ 		
		this.on("afterrender", function(){ 			
			setTimeout(function(){ 				
				Etna.onDone(function(){ 					
					//var btn = this.up("tabpanel").down("form").query("button[iconCls=btn-new]")[0]; 					
					var t = this.down("tabpanel"); 					
					var btn = t.getActiveTab().query("button") && t.getActiveTab().query("button")[0]; 					
					if(!btn.el.dom.onkeydown){ 						
						btn.el.dom.onkeydown = function(e){ 							
							if(btn.fromFocus == "registrationNumber" && /** Tab */ e.keyCode == 9 && !e.shiftKey){ 								
								btn.fromFocus = null; 								
								e.preventDefault();       	         			
								e.stopPropagation();    								
								var form = this.down("tabpanel").down("form[collapsible]"), 										
								formHeader = form.getHeader();	 								
								formHeader.el.dom.querySelector("div.x-tool-after-title").focus(); 							
							} 						
						}.bind(this); 					
					} 					
					this.query("textfield[itemId=registrationNumber]")[0].el.dom.querySelector("input").onkeydown = function(e){  						
						if(/** Tab */ e.keyCode == 9 && !e.shiftKey){ 							
							e.preventDefault();       	         		
							e.stopPropagation();    			        
							btn.focus();       			       
							/** 포커스 CSS 추가 */       			       
							btn.addCls("x-btn-focus");        			        
							btn.addCls("x-btn-default-toolbar-small");      			        
							btn.fromFocus = "registrationNumber"; 						
						} 					
					} 				
				}.bind(this)); 			
			}.bind(this), 1000); 		
		}); 		
		this.callParent(arguments); 	
	} 
});

//2021.03.02 임상근 - pdf 59p : left 메뉴 collapse 버튼 엔터시, expand 버튼으로 포커스 가도록 수정 
Ext.define('Mdi.a11y.view.mdi.LeftViewController', { 	
	override: 'Mdi.view.mdi.LeftViewController', 	
	onLeftMenuAfterRender: function(component, eOpts) {         
		var me = this,             
		view = me.getView().getView(), el;
		
		Ext.create('Ext.tip.ToolTip', {             
			target: view.el,             
			delegate: view.itemSelector,             
			trackMouse: true,             
			renderTo: Ext.getBody(),             
			listeners: {                 
				beforeshow: function(tip) {                     
					if (tip.triggerElement.getAttribute('showtip') !== 'true'){
						return false;                     
					}                     
					var record = view.getRecord(tip.triggerElement);                     
					var text = record.get('text');                     
					tip.update(text);                 
				}             
			}         
		});         
		component.header.el.insertHtml('beforeEnd', '<div class="mdi-left-menu-header-right"></div>');         
		if((el = component.header.el.down('.mdi-left-menu-header-right'))) {         	
			el.destroy();         
		}         
		component.header.el.insertHtml('afterBegin', '<div class="mdi-left-menu-header-left" tabIndex="0"></div>');
		component.header.el.dom.children[0].addEventListener('keydown', function(event) {
			if(event.keyCode === 13) {             
				component.collapse();                 
				setTimeout(function(){                 	
					me.getView().splitter.collapseEl.dom.focus(); // 포커스 이동
					me.getView().splitter.collapseEl.mdiLeftMenuHeaderLeftEl = event.target;
				}.bind(this), 10);             
			}         
		}.bind(this));     
		var leftCollapseImg = component.header.el.dom.querySelector('img');
        leftCollapseImg.setAttribute('alt','사이드 메뉴 접기');
        
        if(this.getView().el.query('img[alt=expand-right]').length !== 0) {
        	this.getView().el.query('img[alt=expand-right]')[0].setAttribute('alt', '사이드 메뉴 펼치기');
        }
	},     
	onTreepanelBeforeCollapse: function(p, direction, animate, eOpts) {         
		var me = this,             
		view = me.getView();         
		if (view.splitter) {         	
				view.splitter.collapseEl.dom.tabIndex = 0;         	
				view.splitter.collapseEl.dom.addEventListener('keydown', function(event) {
				if(event.keyCode === 13) { 	            	
					view.expand(); 	            	
					setTimeout(function(){
						if(view.splitter.collapseEl.mdiLeftMenuHeaderLeftEl) {
							view.splitter.collapseEl.mdiLeftMenuHeaderLeftEl.focus(); // 포커스 이동
						}
					}.bind(this), 10); 	            
				} 	        
			});             
			view.splitter.collapseEl.dom.setAttribute('title', '사이드 메뉴 펼치기');
			view.splitter.setWidth(8);             
			view.splitter.setStyle('display', 'block');         
		}     
	} 
});

//2021.03.02 임상근 체크 박스 ttile 추가, 선택 여부 확인
Ext.override(Ext.form.field.Checkbox, {
	_getTitleText: function() {
		var titleText;
		if (this.config.tooltip) {
			titleText = this.config.tooltip;
		} else if (this.fieldLabel) {
			titleText = this.fieldLabel;
		} else if (this.boxLabel) {
			titleText = this.boxLabel;
		} else {
			titleText = '입력 필드';
		}
		return titleText;
	},
	onRender: function() {
		this.callParent();
		var titleText = this._getTitleText();
		if(this.el.query('input')[0]) {
				this.el.query('input')[0].setAttribute('title', titleText);
		}
		if (this.focusable) {
			this.el.query('input')[0].setAttribute('tabindex', '0');
		}
	},
	onChange: function(value) {
		this.callParent();
		if(!this.el) {
			return;
		}
		var targetComp = this.el.query('input')[0];
		var titleText = this._getTitleText();
		if(targetComp) {
			value ? targetComp.setAttribute('title', titleText+' 선택됨') : targetComp.setAttribute('title', titleText);
		}
	}
});

//2021.03.03 pdf 88page,96page : 팝업이 닫힌 후에 기존 포커스롤 돌아오도록 할 것
//2022.04.12 홍영동 키보드로 포커스 이동시(Tab키) 서브팝업 후 포커스가 고정되게 반영
Ext.define('Ext.override.panel.Panel', {
	override: 'Ext.panel.Panel',
	show: function(animateTarget, cb, scope) {
		this.prevActiveEl = document.activeElement;
		if(this.prevActiveEl && this.prevActiveEl.tagName === 'IFRAME') {
			this.prevActiveEl = document.activeElement.contentDocument.activeElement;
		}
		this.callParent(arguments);
	},
	close: function() {
		this.callParent(arguments);
		if(this.prevActiveEl && this.prevActiveEl.focus) {
			this.prevActiveEl.focus();
		}
	},
	// hide 추가
	//2022.04.12 내용추가된부분
	hide: function() {

		this.callParent(arguments);
		
		if(this.prevActiveEl && this.prevActiveEl.focus){
			if(this.prevActiveEl.dataset.columnid && this.prevActiveEl.dataset.columnid.indexOf('column') !== -1){

				var el = Ext.get(this.prevActiveEl);
				var gridView=  el.up('div.x-grid-view').component;
				var columns = gridView.ownerGrid.moveTabColumns;
				
				if(columns == 'undefined' || columns == null){
					this.prevActiveEl.focus();
				}else{
					for(var i=0; i<=columns.length; i++) {

						if(columns[i] && columns[i].id === this.prevActiveEl.dataset.columnid) {
							gridView.getNavigationModel().column = columns[i]; 

							break;

						}
					}
					gridView.getNavigationModel().focusItem(gridView.getNavigationModel().previousCell);			
				}
			}

			else{
				this.prevActiveEl.focus();
			}
		}

	}
});

//2021.03.03 pdf 77page : 화면 내에서 탭 이동 순서가 이상함
/** 상세 진입 시, 버튼 먼저 포커스 - 수정함 */
Ext.define("Etna.a11y.override.layout.container.Card", { 	
	override: 'Ext.layout.container.Card', 	
	setActiveItem: function(item) {	
		this.callParent(arguments); 		
		setTimeout(function(){ 			// 프로젝트 상황에 맞게 검색 조건 속성을 fieldLabel이 아닌 다른 값으로 해도 무방
			if(this.activeItem && this.activeItem.query) {
				var targetComp = this.activeItem.query("tabpanel, toolbar")[0];
				if (targetComp) {
					switch(targetComp.xtype) {
					case 'tabpanel':
						var tabs = targetComp.query('tab');
						if (tabs && tabs.length > 0) {
							tabs[0].focus();
						}
						break;
					case 'toolbar':
						if (targetComp.dock === "top") {
							var buttons = targetComp.query("button[hidden=false]");
							buttons && buttons[0] && buttons[0].focus();
						}
						break;
					}
				}
			}
			
			if(this.activeItem && this.activeItem.query && this.activeItem.query("tab, textfield, datefield, textarea, checkbox, radio, combo, button, fieldcontainer").length > 1){
				/** [2021.03.16] PDF15 : 홈 > 회원관리 > 회원가입 > '업체회원' / '공동이용사 회원' 클릭 */
				if(this.owner.xtype == 'joinmemberjoin')
				{
					this.activeItem.el && this.activeItem.el.dom && this.activeItem.el.dom.querySelector(".explain-div") && this.activeItem.el.dom.querySelector(".explain-div").focus();
				}else{
					this.activeItem.query("tab, textfield, datefield, textarea, checkbox, radio, combo, button, fieldcontainer")[0].focus(); // Focus 				
				}
			}
		}.bind(this), 10); 	
	} 
});

// 2021.03.09 임상근 그리드 페이징 툴바 내 버튼 title 추가
Ext.define('Etna.override.tooltip.toolbar.Paging', {
	override: 'Ext.toolbar.Paging',
	afterRender: function() {
		this.callParent(arguments);
		this.tooltipToTitle();
	},
	/** 툴팁이 있는 경우, title로 복사 */
	tooltipToTitle: function() {
		var buttons = this.query("button");
		for(var i=0,button; i<buttons.length; i++) {
			button = buttons[i];
			if(Ext.isEmpty(button.el.dom.title) && button.tooltip) {
				button.el.dom.setAttribute('title', button.tooltip);
				if(button.el.dom.dataset.qtip) {
					button.el.dom.removeAttribute('data-qtip');
				}
			}
		}
	}
});

// 2021.03.09 그리드 헤더 컨텍스트 메뉴 닫을 때, 기존 포커스로 돌아오도록 수정
Ext.override(Ext.grid.header.Container, {
	showMenuBy: function(t, header) {
		this.prevActiveEl = document.activeElement;
		this.callParent(arguments);
	},
	onMenuHide: function(menu) {
		this.prevActiveEl && this.prevActiveEl.focus();
		this.callParent(arguments);
	}
});

// 2021.03.10 etna counting toolbar title 수정
Ext.override(Etna.toolbar.Counting, {
	afterRender: function() {
		this.callParent(arguments);
		this.tooltipToTitle();
	},
		/** 툴팁이 있는 경우, title로 복사*/
	tooltipToTitle: function() {
		// 버튼 내용 수정
		var buttons = this.query("button");
		for(var i=0,button; i<buttons.length; i++) {
			button = buttons[i];
			if(Ext.isEmpty(button.el.dom.title) && button.tooltip) {
				button.el.dom.setAttribute('title', button.tooltip);
				if(button.el.dom.dataset.qtip) {
					button.el.dom.removeAttribute('data-qtip');
				}
			}
		}
		// 넘버 필드 수정
		if (this.ownerCt) {
			var parentComp = this.ownerCt;
			var titleText = '';
			if (parentComp && parentComp.xtype === 'gridpanel') {
				titleText += (parentComp.el.dom.getAttribute('aria-label') + ' ');
			}
			titleText += '그리드의 현재 페이지';
			var numberfields = this.query('numberfield');
			for (var i = 0, numberfield; i < numberfields.length; i++) {
				numberfield = numberfields[i];
				if (numberfield) {
					numberfield.el.query('input')[0].setAttribute('title', titleText);
				}
			}
		}
	}
});

//2021.03.10 임상근
/** Window(레이어) 팝업 시, 포커스 빠지지 않도록 처리 */
Ext.define('Etna.override.a11y.Window', {
	override: 'Ext.window.Window',
	onShowComplete: function(cb, scope) {
		this.callParent(arguments);
		
		/** 마지막 엘리먼트 강제 추가 */
		var lastEl = this.el.dom.querySelector("[data-ref=body-last]");
		if(!lastEl.onkeyup){
			lastEl.onkeyup = function(e){
				var buttons = this.query('button[hidden=false]');
				if(buttons && buttons[0]){
					/** 첫번째 포커스로 되돌림 */
					buttons[0].focus();
				}
			}.bind(this);
		}
	},
	renderTpl: [
        // If this Panel is framed, the framing template renders the docked items round the frame 
        '{% this.renderDockedItems(out,values,0); %}',
        '<div id="{id}-body" data-ref="body" class="{baseCls}-body<tpl if="bodyCls"> {bodyCls}</tpl>',
            ' {baseCls}-body-{ui}<tpl if="uiCls">',
                '<tpl for="uiCls"> {parent.baseCls}-body-{parent.ui}-{.}</tpl>',
            '</tpl>{childElCls}"',
            '<tpl if="bodyRole"> role="{bodyRole}"<tpl else> role="presentation"</tpl>',
            '<tpl if="bodyStyle"> style="{bodyStyle}"</tpl>>',
            '{%this.renderContainer(out,values);%}',
        '</div>',
        '{% this.renderDockedItems(out,values,1); %}',
        '<div id="{id}-body-last"  data-ref="body-last" tabindex="0"></div>' // 마지막 포커스 추가
    ]
});

Ext.define('Etna.override.a11y.ZIndexManager', {
	override: 'Ext.ZIndexManager',
	_showModalMask: function (comp) {
		comp.floatParent = null;
		this.callParent([comp]);
	}
});

//2021.03.15 임상근 top 메뉴의 로그인 버튼을 눌렀을 때 동작
Ext.define('Mdi.a11y2.view.mdi.TopViewController', {
	override: 'Mdi.view.mdi.TopViewController',
	onMdiCertLogInButtonClick : function (){
		if(isForeign){
			MdiManager.toggleSpMain(isForeign);
		}else{
			var me = this, KepcoLoginRef = me.lookupReference('KepcoLoginRef');
			/** 현재 itemId가 지정되어 있지 않아, 찾을수 잇는 방법이 text밖에 없음 */
			var restoreFocusEl = this.view.query("button[text=로그인]")[0];
			if(!KepcoLoginRef.$close){
				KepcoLoginRef.$close = KepcoLoginRef.close;
			}
			KepcoLoginRef.close = function(){
				KepcoLoginRef.$close(); // 기존 클로즈 펑션 호출
				restoreFocusEl.focus(); // 포커스 이동
			};
			KepcoLoginRef.show();
			KepcoLoginRef.center();
			if(document.querySelector('#kepcoLoginPop')) {
				KepcoLoginRef.setFocusToComponent();
			}
		}
	}
	
});


//2021.03.15 임상근 상단 툴바내의 버튼으로 포커스 안감
/** [2021.03.15] 상단 툴바내의 버튼으로 포커스 안감 */
Ext.define('Etna.override.moveTab2.toolbar.Toolbar', {
	override: 'Ext.toolbar.Toolbar',   
	firstActiveItemIndex:null,
	onFocusableContainerFocus: function(e) {
		this.callParent(arguments);
		this.activateButtons();
	},
	onFocusableContainerFocusEnter: function(e) {
		this.callParent(arguments);
		this.activateButtons();
	},
	onFocusableContainerFocusLeave: function(e) {
		this.callParent(arguments);
		this.deactivateButtons();
	},
	/** Tab Key Move */
	activateButtons: function(){
		var items = this.getFocusables();
		var tabIndexList = [];
		for (var i = 0, item; i < items.length; i++) {
			item = items[i];
			if(item.disabled != true && item.hidden == false && item.getHeight() > 0 && item.getWidth() > 0){
				tabIndexList.push(i);
				if(item.getTabIndex() != this.activeChildTabIndex){	
					item.setTabIndex(this.activeChildTabIndex);
				}
			}else{
				// 선택 불가능한 항목 포커스 안가도록 처리(tabindex=-1)
				item.setTabIndex(this.inactiveChildTabIndex);
			}
		}
		this.firstActiveItemIndex = tabIndexList[0];
		//this.firstActiveItemId = items[this.firstActiveItemIndex].id;
	},
	//** Restore Child */
	deactivateButtons: function(){
		var items = this.getFocusables();
		var panelCandidate = this.up("panel");
		if(panelCandidate){
			var isFloating = panelCandidate.floating;	
		}
  	
		/** isFloating 여부 */
		if(isFloating){
			for (var i = 0, item; i < items.length; i++) {
				item = items[i];  		
				if(item.disabled != true && item.hidden == false && item.getHeight() > 0 && item.getWidth() > 0){
					if(item.getTabIndex() != this.inactiveChildTabIndex){
						item.setTabIndex(this.activeChildTabIndex);
					}
				}
			}
			/** 최초에 포커스 들어간 엘리먼트 인덱스 */
			if(!Ext.isEmpty(this.firstActiveItemIndex) && items.length > 0){
				/** floating:true -> tabindex:-1 */
				items[this.firstActiveItemIndex].setTabIndex(this.inactiveChildTabIndex);
			}
		}else{
			for (var i = 0, item; i < items.length; i++) {
				item = items[i];  			  		
				if(item.getTabIndex() != this.inactiveChildTabIndex){
					item.setTabIndex(this.inactiveChildTabIndex);
				}
			}
			/** 최초에 포커스 들어간 엘리먼트 인덱스 */
			if(!Ext.isEmpty(this.firstActiveItemIndex) && items.length > 0){
				/** floating:false -> tabindex:0 */
				items[this.firstActiveItemIndex].setTabIndex(this.activeChildTabIndex); 
			}
		}
	}
});

//2021.03.16 임상근 
/** [2021.03.16] PDF 23 : 첨부파일 스페이스키로 인한, 삭제 시 포커스 빠지는 현상 조치 */
/** [2] 웹접근성 제거대상(첨부파일 종속) : [2021.03.16] PDF 23 : 첨부파일 스페이스키로 인한, 삭제 시 포커스 빠지는 현상 조치[TECHSUPP-2133] */
//2022.04.28 Hoon 웹접근성 관련 롤백 구간3
//Ext.define('Etna.override.a11y2.upload.StoreBasedUploader', {
//	override: 'Etna.upload.StoreBasedUploader',
//	a11yInit: function(){
//		this.callParent(arguments);
//		
//		/** 키보드 이벤트 활성화 */
//		if(!this.container.dom.onkeydown){
//			this.container.dom.onkeydown = this.onKeyDownHandler.bind(this);
//		}		
//	},
//	onKeyDownHandler: function(e){
//		if(/** Space */ e.keyCode == 32){
//			this.onDeleteKeyHandler(e);
//		}
//	},
//		/** 체크박스 컬럼헤더 엔터 처리 */
//	a11yCheckColumnHeader: function(e){
//		var header = this.down("headercontainer");
//		var columns = header.columnManager.columns;
//		for(var i=0; columns && i<columns.length; i++){
//			if(columns[i].el.dom.innerText.indexOf("삭제") >= 0){
//				this.checkedColumn = columns[i];
//				this.checkedColumn.el.on({ keydown : function(e){
//					if(e.keyCode === 13 || /** Space */ e.keyCode == 32) {
//						this.selectAllFiles();
//					}
//				}.bind(this) })
//				return;
//			}
//		}
//	}
//});
//웹접근성 관련 롤백 구간3 끝 
// 2021.03.17 임상근 전문가 상세 보고서 20p. 토글의 선택 여부 확인 불가
Ext.override(Etna.form.field.Toggle, {
	_generateTitleText: function(isOn, pressed) {
		var me = this;
		var titleText = me.config.prefix ? me.config.prefix + '의 ' : '';
		var selectedText = (isOn) ? me.onText : me.offText;
		var pressedText = pressed ? ' 항목이 선택됨' : ' 항목';
		return titleText + selectedText + pressedText;
	},
	afterRender: function() {
		this.callParent(arguments);
		var segbtn = this.down('segmentedbutton');
		if (segbtn && segbtn.items && segbtn.items.items) {
			var items = segbtn.items.items;
			for (var i = 0; i < items.length; i++) {
				var item = items[i];
				if (item.el) {
					var isOn, pressed;
					if (item.role === 'on') {
						isOn = true;
						pressed = (this.getValue() === this.onValue);
					} else if (item.role === 'off') {
						isOn = false;
						pressed = (this.getValue() === this.offValue);
					}
					var titleText = this._generateTitleText(isOn, pressed);
					item.el.dom.setAttribute('title', titleText);
				}
			}
		}
	},
	onButtonToggle : function(btn, pressed){
		var me = this;
		if(pressed){
			var value = btn.role == 'on' ? me.onValue : me.offValue;
			me.setValue(value);
		}
		if (btn.el) {
			var titleText = me._generateTitleText(btn.role === 'on', pressed);
			btn.el.dom.setAttribute('title', titleText);
		}
	}
});

/**************************************************************************************/
/************************** 2021.03.17 반영추가 *****************************************/
/**************************************************************************************/
/** [2021.03.17] PDF25 Top메뉴 H태그 추가 */
Ext.define('Mdi.a11y2.view.mdi.TopViewController', { 	
	override: 'Mdi.view.mdi.TopViewController', 
	createMenuItems: function(childNodes) {
		var me = this,
			menuItems = [];
		Ext.Array.each(childNodes, function(node) {
			if(node.get('code').indexOf('SEARCH') != -1) {
				return;
			}

			node.raw.htagStart = '<h'+(node.raw.depth+3)+' style="display:inline;;font-size:12px;">';
			node.raw.htagEnd = '</h'+(node.raw.depth+3)+'>';
    	
			menuItems.push({
				text: node.get('text'),
				border: false,
				handler: me.onMenuHander,
				scope: me,
				menuData: node,
				menu: node.isLeaf() ? null : {
					xtype: 'menu',
					frame: false,
					plain: true,
					ui: 'mdi-top-menu-sub',
					items: me.createMenuItems(node.childNodes)
				}
			});
		});
		return menuItems;
	}
});

/** [2021.03.16] PDF26 : Left메뉴 H태그 추가 */
Ext.define('Etna.override.a11y.tree.Column', {
	override: 'Ext.tree.Column',
	cellTpl: [
      '<tpl for="lines">',
          '<img src="{parent.blankUrl}" class="{parent.childCls} {parent.elbowCls}-img ',
          '{parent.elbowCls}-<tpl if=".">line<tpl else>empty</tpl>" role="presentation"/>',
      '</tpl>',
      '<img src="{blankUrl}" class="{childCls} {elbowCls}-img {elbowCls}',
          '<tpl if="isLast">-end</tpl><tpl if="expandable">-plus {expanderCls}</tpl>" role="presentation"/>',
      '<tpl if="checked !== null">',
          '<input type="button" {ariaCellCheckboxAttr}',
              ' class="{childCls} {checkboxCls}<tpl if="checked"> {checkboxCls}-checked</tpl>"/>',
      '</tpl>',
      '<img src="{blankUrl}" role="presentation" class="{childCls} {baseIconCls} ',
          '{baseIconCls}-<tpl if="leaf">leaf<tpl else>parent</tpl> {iconCls}"',
          '<tpl if="icon">style="background-image:url({icon})"</tpl>/>',
      '<tpl if="href">',
          '<a href="{href}" role="link" target="{hrefTarget}" class="{textCls} {childCls}">{value}</a>',
      '<tpl else>',
          '<span class="{textCls} {childCls}"> {record.data.htagStart} {value} {record.data.htagEnd} </span>',
      '</tpl>'
  ],
  treeRenderer: function(value, metaData, record, rowIdx, colIdx, store, view){
      var me = this,
          cls = record.get('cls'),
          rendererData;

      if (metaData && cls) {
          metaData.tdCls += ' ' + cls;
      }
      
	  rendererData = me.initTemplateRendererData(value, metaData, record, rowIdx, colIdx, store, view);
      if(this.up("panel") && this.up("panel").xtype === "mdileft"){
	      rendererData.record.data.htagStart = '<h'+(rendererData.record.data.depth+3)+' style="display:inline;font-size:12px;">';
	      rendererData.record.data.htagEnd = '</h'+(rendererData.record.data.depth+3)+'>';
      }else{
    	  rendererData.record.data.htagStart = '';
	      rendererData.record.data.htagEnd = '';
      }
      return me.getTpl('cellTpl').apply(rendererData);
  }
});

Ext.define('Etna.override.a11y.panel.Title', {
    override: 'Ext.panel.Title',
    renderTplTemp: 
    	 '<tpl if="iconMarkup && iconBeforeTitle">{iconMarkup}</tpl>' +
        
        '<h3 id="{id}-textEl" data-ref="textEl" class="{textCls} {textCls}-{ui} {itemCls}{childElCls}" unselectable="on"' +
            '<tpl if="headerRole">' +
                ' role="{headerRole}"' +
            '</tpl>' +
        '>{text}</h3>' +
        '<tpl if="iconMarkup && !iconBeforeTitle">{iconMarkup}</tpl>',
        
		initComponent: function(){
			if(this.ui === "mdi-left"){
				this.renderTpl = this.renderTplTemp;
			}
			this.callParent(arguments);
		}
});


/** [2021.03.17] 현재 Tab 경로 */
//2021.03.23 - 2021.03.18 전달내용과 겹치는 관계로 주석처리함.
/*Ext.define('Etna.override.a11y.toolbar.Breadcrumb', {
	override: 'Ext.toolbar.Breadcrumb',
	onFocusableContainerFocus: function(e) {
		this.callParent(arguments);
		var focusEls = this.getFocusables();
		if(focusEls && focusEls[0]){
			this.getFocusables()[0].setTabIndex(this.activeChildTabIndex);
			this.getFocusables()[0].focus();	
		}
	},
	deactivateFocusable: function(child,  optional  newTabIndex) {
		if(this.getTabIndex() === this.activeChildTabIndex){
			this.setTabIndex(this.inactiveChildTabIndex)
		}
		child.setTabIndex(0);
	}
});*/


/** [2021.03.17] MDI 탭바 탭키이동 및 Close버튼 포커스/삭제가능 처리 */
// 2021.03.23 - 2021.03.18 전달내용과 겹치는 관계로 주석처리함.
/*Ext.define('Etna.override.a11y.tab.Bar', {
	override: 'Ext.tab.Bar',
  onAdd: function(tab, pos) {
	    this.callParent([tab, pos]);
	    tab.on("afterrender", this.afterTabRender.bind(this));
	},
	afterTabRender: function(comp, e){
		if(!comp.el.dom.onkeydown){
			comp.el.dom.onkeydown = function(e){
				if(*//** Tab *//*e.keyCode == 9 && !e.shiftKey){
					this.findCloseEl(e);
				}else if(*//** Enter *//*e.keyCode == 13){
					if(this.ownerCt && this.ownerCt.xtype == "tabpanel"){
						if(e.target == this.activeTab.el.dom){
							this.findFocusOnActiveTab(e);
						}else{
							var mdiviewport = this.ownerCt.up("mdiviewport");
							if(mdiviewport && mdiviewport.down("mdileft")){
								mdiviewport.down("mdileft").restoreFocusTabbar = true;
							}
						}
					}
				}
			}.bind(this);
		}
	},
	findFocusOnActiveTab: function(e){
		var tabPanel = this.ownerCt;
		if(tabPanel.activeTab){
			e.preventDefault(); 				
			e.stopPropagation(); 	
			var focusableEl = tabPanel.activeTab.query("tab, textfield, datefield, textarea, checkbox, radio, combo, button, fieldcontainer");
			if(focusableEl && focusableEl.length > 0){
				focusableEl[0].focus();
			}
		}
	},
	findCloseEl: function(e){
		var closeBtn = e.target.querySelector("span.x-tab-close-btn");
		if(closeBtn){
			e.preventDefault(); 				
			e.stopPropagation();
			// 추가
			var textEl = e.target.querySelector("span[data-ref='btnInnerEl']");
			if(textEl && textEl.innerText){
				closeText = textEl.innerText + " 닫기 버튼 ";
			}
			closeBtn.setAttribute("title", closeText);
			closeBtn.setAttribute("tabindex", 0);
			closeBtn.focus();
			if(!closeBtn.onkeydown){
				closeBtn.onkeydown = function(e){
					if(*//** Enter *//*e.keyCode == 13){
						e.preventDefault(); 				
						e.stopPropagation(); 
						for(var i=0; i<this.items.items.length; i++){
							var tab = this.items.items[i];
							if(tab.el.dom.querySelector("span.x-tab-close-btn") == e.target){
								this.closeTab(tab);
								setTimeout(function(){
									if(this.items.items.length > 0){
										var item = this.items.items[i];
										if(!item){
											item = this.items.items[i-1];
										}
										item.focus();
										
									}else{
										var items = this.el.query("a[title='사이드 메뉴 펼치기']");
										items && items[0] && items[0].focus();
								
									}
									var mdiviewport = this.ownerCt.up("mdiviewport");
									if(mdiviewport && mdiviewport.down("mdileft")){
										mdiviewport.down("mdileft").restoreFocusTabbar = true;
									}
								}.bind(this), 10);
								return;
							}
						}
					}
				}.bind(this);
			}
		}
	},
	onFocusableContainerFocus: function(e) {
  	this.callParent(arguments);
  	this.activateButtons();
	},
	onFocusableContainerFocusEnter: function(e) {
		this.callParent(arguments);
		this.activateButtons();
	},
	onFocusableContainerFocusLeave: function(e) {
		this.callParent(arguments);
		this.deactivateButtons();
	},
	
	*//** Tab Key Move *//*
  activateButtons: function(){
  	var items = this.getFocusables();
  	var tabIndexList = [];
  	for (var i = 0, item; i < items.length; i++) {
  		item = items[i];
  		if(item.disabled != true && item.hidden == false && item.getHeight() > 0 && item.getWidth() > 0){
  			tabIndexList.push(i);
  			if(item.getTabIndex() != this.activeChildTabIndex){	
	  			item.setTabIndex(this.activeChildTabIndex);
	  		}
  		}else{
  			// 선택 불가능한 항목 포커스 안가도록 처리(tabindex=-1)
  			item.setTabIndex(this.inactiveChildTabIndex);
  		}
  	}
  	this.firstActiveItemIndex = tabIndexList[0];
  },
  
  *//** Restore Child *//*
  deactivateButtons: function(){
  	var items = this.getFocusables();
  	var panelCandidate = this.up("panel");
  	
  	*//** isFloating 여부 *//*
  	
		for (var i = 0, item; i < items.length; i++) {
  		item = items[i];  		
  		if(item.disabled != true && item.hidden == false && item.getHeight() > 0 && item.getWidth() > 0){
  			if(item.getTabIndex() != this.inactiveChildTabIndex){
  				item.setTabIndex(this.activeChildTabIndex);
  			}
  		}
  	}
  	*//** 최초에 포커스 들어간 엘리먼트 인덱스 *//*
  	if(!Ext.isEmpty(this.firstActiveItemIndex) && items[this.firstActiveItemIndex]){
  		*//** floating:true -> tabindex:-1 *//*
  		items[this.firstActiveItemIndex].setTabIndex(this.inactiveChildTabIndex);
  	}
  	
  },
  
  beforeFocusableChildFocus: function(child) {
      var me = this;
      me.activateFocusable(child);
      if (child.needArrowKeys) {
          me.guardFocusableChild(child);
      }
  }  
});*/
/** [2021.03.17] PDF9,10에서 키보드를 통한, 탭활성화 시 레프트메뉴 활성화 후 이전 포커스 찾아가도록 함 */
/** [3] 웹접근성 제거대상[오동작 위험] : [2021.03.17] PDF9,10에서 키보드를 통한, 탭활성화 시 레프트메뉴 활성화 후 이전 포커스 찾아가도록 함[TECHSUPP-2140] */
//2022.04.28 Hoon 웹접근성 관련 롤백 구간4
//Ext.define('Mdi.override.a11y.view.mdi.LeftViewController', {
//	override: 'Mdi.view.mdi.LeftViewController',
//	onCurrentMenuChange: function(menu, oldMenu) {
//		if(this.view.restoreFocusTabbar){
//			var preActiveEl = document.activeElement;
//			this.callParent(arguments);
//			setTimeout(function(){
//				preActiveEl.focus();
//			}, 10);
//		}else{
//			this.callParent(arguments);
//		}
//	}
//});
//웹접근성 관련 롤백 구간4 끝 

Ext.define('Etna.override.a11y.button.Button', {
	override: 'Ext.button.Button',
	autoEl: {
		tag: 'a',
		role: 'button'
	}	
});


/**************************************************************************************/
/************************** 2021.03.18 반영추가 *****************************************/
/**************************************************************************************/
/** 모든 버튼에 대한 키이벤트 */
/** [4] 웹접근성 제거대상[오동작 위험] : 모든 버튼에 대한 키이벤트[TECHSUPP-2140]  */
//2022.04.28 Hoon 웹접근성 관련 롤백 구간5
//Ext.override(Ext.button.Manager, {
//	init: function() {
//      var me = this;
//      if (!me.initialized) {
//          Ext.getDoc().on({
//              focusin: me.onFocusIn,
//              keyup: me.onDocumentKeyDown,
//              mouseup: me.onDocumentMouseUp,
//              scope: me
//          });
//          me.initialized = true;
//      }
//  },
//  onDocumentKeyDown: function(e) {
//  	var k = e.getKey();
//    // SPACE and ENTER trigger a click 
//    if (this.enableEnter && (k === e.SPACE || k === e.ENTER)) {
//			this.callParent(arguments);
//		}else{
//			this.enableEnter = true;
//		}
//  },
//  onFocusIn: function(e){
//  	this.enableEnter = false;
//  	setTimeout(function(){
//  		this.enableEnter = true;
//  	}.bind(this), 500);
//  }
//});
//
////[1] 중복정의로 인한 제거 : 2021.03.04 임상근 - LEFT 메뉴, TOP 메뉴 탭이동 소스 반영[TECHSUPP-2136]
//Ext.define('Mdi.view.override2.mdi.LeftViewController', {
//	prevFocusOutElmentSelector: '.mdi-left-menu-header-left',
//	nextFocusOutElmentSelector: '.x-tab-active',
//	override: 'Mdi.view.mdi.LeftViewController',
//	setMenu: function(menuData) {
//		this.callParent(arguments);
//		this.a11yInit();
//		},
//	a11yInit: function(){
//		this.treeContainer = this.view.el.dom.querySelector(".x-grid-item-container");
//		if(this.treeContainer == null){
//			setTimeout(function(){
//				this.a11yInit();
//			}.bind(this), 1000);
//			return;
//		}
//		/** Expand SubMenu */
//		if(!this.treeContainer.onkeyup){
//			this.treeContainer.onkeyup = function(e){
//				e.preventDefault();
//				e.stopPropagation();
//				var record = this.view.selModel.navigationModel.position.record;
//				if(/** TabKey */e.keyCode == 9 && e.shiftKey == false){
//					if(record && record.data.children && record.data.children.length > 0 && record.expand){
//						record.expand();
//						// alt 초기화 방지를 위해서 호출
//						this.adjustWidth();
//					}
//				}else if(/** TabKey */e.keyCode == 9 && e.shiftKey == true){
//					if(record && record.data.children && record.data.children.length > 0 && record.expand){
//						record.expand();
//						// alt 초기화 방지를 위해서 호출
//						this.adjustWidth();
//					}
//				}
//				// 신규 추가항목 ================================
//				else if (e.keyCode == 13) {
//					if(record && record.data.children && record.data.children.length === 0) {
//						this.onMdiLeftMenuOpenUsingKeyboard(this.getView(), record);
//					}
//				}
//				// 신규 추가항목 ================================
//			}.bind(this);
//		}
//		/** Move Next Menu */
//		if(!this.treeContainer.onkeydown){
//			this.treeContainer.onkeydown = function(e){
//				if(/** TabKey */e.keyCode == 9 && e.shiftKey == false){
//					this.a11yTabkeyDownHandler(e);
//				} else if(e.keyCode == 9 && e.shiftKey == true){
//					this.a11yUnTabkeyDownHandler(e);
//				}
//			}.bind(this);
//		}
//	},
//	a11yTabkeyDownHandler: function(e){
//		e.preventDefault();
//		e.stopPropagation();
//		/** 마지막 로우(포커스가 밖으로 나가야 됨) */
//		if(this.view.selModel.store.data.items.length-1 == this.view.selModel.navigationModel.position.rowIdx){
//			var next = document.querySelector(this.nextFocusOutElmentSelector);
//			next.focus();
//		} else{
//			var navModel = this.view.selModel.navigationModel;
//			var idx = navModel.position.rowIdx+1;
//			this.view.selModel.select(idx);
//			this.view.selModel.navigationModel.position.rowIdx = idx;
//			//this.view.selModel.navigationModel.position.colIdx = 0;
//			//this.view.selModel.navigationModel.position.column = navModel.column;
//			//this.view.selModel.navigationModel.position.record = this.view.selModel.store.data.items[idx];
//			this.view.selModel.navigationModel.setPosition(this.view.selModel.navigationModel.position);
//		}
//	},
//	a11yUnTabkeyDownHandler: function(e){
//		e.preventDefault();
//		e.stopPropagation();
//		/** 첫번째 로우(포커스가 밖으로 나가야 됨) */
//		if(this.view.selModel.navigationModel.position.rowIdx == 0){
//			var prev = document.querySelector(this.prevFocusOutElmentSelector);
//			prev.focus();
//		}else{
//			this.view.selModel.select(this.view.selModel.navigationModel.position.rowIdx-1);
//		}
//	}
//});
//
///** [5] 웹접근성 제거대상(첨부파일 종속) : 센스리더기 활성화 시, 첨부파일 삭제컬럼 삭제 안되는 현상 조치[TECHSUPP-2133] */
//Ext.define('Etna.override.a11y3.upload.StoreBasedUploader', {
//	override: 'Etna.upload.StoreBasedUploader',
//	onDeleteKeyHandler: function(e){
//		var el = e.target;
//		var dataviews = el.parentElement.querySelectorAll(".x-etna-dataview-item");
//		if(dataviews.length > 0){
//			console.log("onDeleteKeyHandler if");
//			/** Image(Data) View */
//			el = this.body.dom.querySelector(".x-view-item-focused");
//			for(var i=0; i<dataviews.length; i++){
//				if(el == dataviews[i]){
//					if(el.querySelector(".local")){
//						e.preventDefault();
//						e.stopPropagation();
//						
//						setTimeout(function(){
//							var view = this.getView();
//							var sm = view.getSelectionModel();
//							var record = sm.store.data.items[i] || sm.store.data.items[i-1];
//							sm.setLocked(false);
//							sm.select(record, true);
//							sm.setLocked(true);
//						}.bind(this), 10);
//						this.removeFile(this.getAttachedFiles()[i].id);
//						if(!this.files || this.files.length < 1){
//							this.setHeaderFocus()
//						}
//					}
//					return;
//				}
//			}	
//		}else{
//			/** List View */
//			var listview = this.body.dom.querySelectorAll(".x-grid-cell-row-checker");
//			for(var i=0; i<listview.length; i++){
//				if("&nbsp;" == el.innerHTML){
//					el = el.parentElement.parentElement;
//				}
//				if(el == listview[i]){
//					if(el.parentElement.querySelector(".x-etna-grid-uploader-status-local")){
//						e.preventDefault();
//						e.stopPropagation();
//						
//						/** NavigationModel을 사용한 포커스 이동 */
//						var panel = this.down("panel");
//						var selModel = panel.getSelectionModel();
//						
//						/** 포커스 처리 */
//							selModel.select(i);
//							selModel.navigationModel.position.rowIdx = i;
//							selModel.navigationModel.position.colIdx = 0;
//							selModel.navigationModel.position.column = selModel.column;
//							selModel.navigationModel.position.record = selModel.store.data.items[i];
//							selModel.navigationModel.setPosition(selModel.navigationModel.position);
//					}
//					if(!this.files || this.files.length < 1){
//						setTimeout(function(){
//							this.setHeaderFocus();
//						}.bind(this), 100);
//					}	
//					return;
//				}
//			}
//		}
//	}
//});
//웹접근성 관련 롤백 구간5 끝 
/** [2021.03.18] 현재 Tab 경로 */
Ext.define('Etna.override.a11y.toolbar.Breadcrumb', {
	override: 'Ext.toolbar.Breadcrumb',
	onFocusableContainerFocus: function(e) {
		this.callParent(arguments);
		var focusEls = this.getFocusables();
		if(focusEls && focusEls[0]){
			this.getFocusables()[0].setTabIndex(this.activeChildTabIndex);
			this.getFocusables()[0].focus();	
		}
	},
	deactivateFocusable: function(child, /* optional */ newTabIndex) {
		if(this.getTabIndex() === this.activeChildTabIndex){
			this.setTabIndex(this.inactiveChildTabIndex)
		}
		child.setTabIndex(0);
	}
});
/** [2021.03.17] MDI 탭바 탭키이동 및 Close버튼 포커스/삭제가능 처리 */
Ext.define('Etna.override.a11y.tab.Bar', {
	override: 'Ext.tab.Bar',
	// initComponent, onChange 추가
	initComponent: function() {
		this.on("change", this.onChange);
		this.callParent(arguments);
	},
	onChange: function(e) {
		var tabItems = this.items.items;
		for(var i=0; i<tabItems.length; i++) {
			var item = tabItems[i];

			if(item.rendered) {
				item.el.dom.setAttribute('title', item.title.replace(' 선택됨', ''));
				if(item === this.activeTab) {
					item.el.dom.setAttribute('title', item.title + ' 선택됨')
				}
			} else {
				if(item === this.activeTab) {
					item.setConfig('title', item.title + ' 선택됨')
				}
			}
		}
	},
	
	onAdd: function(tab, pos) {
	    this.callParent([tab, pos]);
	    tab.on("afterrender", this.afterTabRender.bind(this));
	},
	
	afterTabRender: function(comp, e){
		
		if(Ext.isIE11){
			if(!comp.el.dom.onkeydown){
				comp.el.dom.onkeydown = function(e){
					this.onFindCloseEl(e);
					this.onActiveTab(e);
				}.bind(this);
			}
			if(!comp.el.dom.onkeyup){
				comp.el.dom.onkeyup = this.onActiveTab.bind(this);
			}
		}else{
			if(!comp.el.dom.onkeydown){
				comp.el.dom.onkeydown = function(e){
					this.onFindCloseEl(e);
					this.onActiveTab(e);
				}.bind(this);
			}
		}
		// 초기 선택된 Component의 title에 선택됨 추가를 위해 아래 소스 추가
		var tabItems = this.items.items;

		for(var i=0; i<tabItems.length; i++) {
			var item = tabItems[i];
			if(item.rendered) {
				item.el.dom.setAttribute('title', item.title.replace(' 선택됨', ''));
				if(item === this.activeTab) {
					item.el.dom.setAttribute('title', item.title + ' 선택됨');
				}
			} else {
				item.setConfig('title', item.title.replace(' 선택됨', ''));
				if(item === this.activeTab) {
					item.setConfig('title', item.title + ' 선택됨');
				}
			}
		}
	},
	
	/** 탭키를 활용한 닫기버튼 찾기 */
	onFindCloseEl: function(e){
		if(/** Tab */e.keyCode == 9 && !e.shiftKey){
			this.findCloseEl(e);
		}
	},
	
	/** 탭 활성화 */
	onActiveTab: function(e){
		if(/** Enter */e.keyCode == 13){
			var targetEl = e.target;
			if(this.ownerCt && this.ownerCt.xtype == "tabpanel"){
				/** 현재탭 */
				if(targetEl == this.activeTab.el.dom){
					this.findFocusOnActiveTab(e);
				}else{
					/** 다른탭 */
					if(Ext.isIE11){
						var tabPanel = this.up();
						var tabs = this.items.items;
						for(var i=0; i<tabs.length; i++){
							if(e.target.id === tabs[i].id){
								e.preventDefault(); 				
								e.stopPropagation(); 	
								tabPanel.setActiveTab(tabs[i].card);
								break;
							}
						}
					}
					var mdiviewport = this.ownerCt.up("mdiviewport");
					if(mdiviewport && mdiviewport.down("mdileft")){
						mdiviewport.down("mdileft").restoreFocusTabbar = true;
					}
				}
			}
		}
	},
	
	findFocusOnActiveTab: function(e){
		var tabPanel = this.ownerCt;
		if(tabPanel.activeTab){
			e.preventDefault(); 				
			e.stopPropagation(); 	
			var focusableEl = tabPanel.activeTab.query("tab, textfield, datefield, textarea, checkbox, radio, combo, button, fieldcontainer");
			if(focusableEl && focusableEl.length > 0){
				focusableEl[0].focus();
			}
		}
	},
	findCloseEl: function(e){
		var closeBtn = e.target.querySelector("span.x-tab-close-btn");
		if(closeBtn){
			e.preventDefault(); 				
			e.stopPropagation(); 	
			closeBtn.setAttribute("tabindex", 0);
			closeBtn.focus();
			if(!closeBtn.onkeydown){
				closeBtn.onkeydown = function(e){
					if(/** Enter */e.keyCode == 13){ 
						e.preventDefault(); 				
						e.stopPropagation(); 
						for(var i=0; i<this.items.items.length; i++){
							var tab = this.items.items[i];
							if(tab.el.dom.querySelector("span.x-tab-close-btn") == e.target){
								this.closeTab(tab);
								setTimeout(function(){
									if(this.items.items.length > 0){
										var item = this.items.items[i];
										if(!item){
											item = this.items.items[i-1];
										}
										item.focus();
										
									}else{
										var items = this.el.query("a[title='사이드 메뉴 펼치기']");
										items && items[0] && items[0].focus();
								
									}
									var mdiviewport = this.ownerCt.up("mdiviewport");
									if(mdiviewport && mdiviewport.down("mdileft")){
										mdiviewport.down("mdileft").restoreFocusTabbar = true;
									}
								}.bind(this), 10);
								return;
							}
						}
					}
				}.bind(this);
			}
		}
	},
	onFocusableContainerFocus: function(e) {
  	this.callParent(arguments);
  	this.activateButtons();
	},
	onFocusableContainerFocusEnter: function(e) {
		this.callParent(arguments);
		this.activateButtons();
	},
	onFocusableContainerFocusLeave: function(e) {
		this.callParent(arguments);
		this.deactivateButtons();
	},
	
	/** Tab Key Move */
  activateButtons: function(){
  	var items = this.getFocusables();
  	var tabIndexList = [];
  	for (var i = 0, item; i < items.length; i++) {
  		item = items[i];
  		if(item.disabled != true && item.hidden == false && item.getHeight() > 0 && item.getWidth() > 0){
  			tabIndexList.push(i);
  			if(item.getTabIndex() != this.activeChildTabIndex){	
	  			item.setTabIndex(this.activeChildTabIndex);
	  		}
  		}else{
  			// 선택 불가능한 항목 포커스 안가도록 처리(tabindex=-1)
  			item.setTabIndex(this.inactiveChildTabIndex);
  		}
  	}
  	this.firstActiveItemIndex = tabIndexList[0];
  },
  
  /** Restore Child */
  deactivateButtons: function(){
  	var items = this.getFocusables();
  	var panelCandidate = this.up("panel");
  	
  	/** isFloating 여부 */
  	
		for (var i = 0, item; i < items.length; i++) {
  		item = items[i];  		
  		if(item.disabled != true && item.hidden == false && item.getHeight() > 0 && item.getWidth() > 0){
  			if(item.getTabIndex() != this.inactiveChildTabIndex){
  				item.setTabIndex(this.activeChildTabIndex);
  			}
  		}
  	}
  	/** 최초에 포커스 들어간 엘리먼트 인덱스 */
  	if(!Ext.isEmpty(this.firstActiveItemIndex) && items[this.firstActiveItemIndex]){
  		/** floating:true -> tabindex:-1 */
  		items[this.firstActiveItemIndex].setTabIndex(this.inactiveChildTabIndex);
  	}
  	
  },
  
  beforeFocusableChildFocus: function(child) {
      var me = this;
      me.activateFocusable(child);
      if (child.needArrowKeys) {
          me.guardFocusableChild(child);
      }
  }  
});

/********** 2021.03.19 임상근 *********/
/** [6] 웹접근성 제거대상(4. 그리드 체크박스에 체크시 오류나는 경우 있음) : 2021.03.19 임상근[TECHSUPP-2140]  */
//2022.04.28 Hoon 웹접근성 관련 롤백 구간6
//Ext.define('Etna.override.moveTab.grid.NavigationModel', {
//	override: 'Ext.grid.NavigationModel',
//	onKeyTabOriginal : function(keyEvent){
//			var view = keyEvent.position.view,
//				selModel = view.getSelectionModel(),
//				editingPlugin = view.editingPlugin;
//
//      // If we were in editing mode, but just focused on a non-editable cell, behave as if we tabbed off an editable field 
//      if (editingPlugin && selModel.wasEditing) {	
//          keyEvent.preventDefault();
//          selModel.onEditorTab(editingPlugin, keyEvent);
//      } else {
//          return this.callParent([keyEvent]);
//      }
//		return;
//	},
//	onKeyTab: function(keyEvent) {	
//		var grid = this.view.ownerGrid;
//		var lastRecordIdx = grid.getStore().data.length-1;
//		var firstRecordIdx = 0;
//		var currentRecordIdx = this.position.rowIdx;
//		
//		if(this.column){
//			var lastColumnIdx = grid.moveTabColumns.length-1;
//			/** 마지막 */
//			if(grid.moveTabColumns[lastColumnIdx].id == this.column.id){
//				if(lastRecordIdx == currentRecordIdx){
//					this.onKeyTabOriginal(keyEvent);
//					return;
//				}
//			}
//			/** 첫번째 */
//			else if(keyEvent.shiftKey && grid.moveTabColumns[firstRecordIdx].id == this.column.id){
//				if(firstRecordIdx == currentRecordIdx){
//					this.onKeyTabOriginal(keyEvent);
//					return;
//				}
//			}
//		}else{
//			this.onKeyTabOriginal(keyEvent);
//			return;
//		}
//		
//		//console.log("using keyboard : onKeyTab");
//		
//		/** 탭이동 컬럼이 아니면, 처음으로 */
//		if(!this.isMoveTabColumn(this.column)){
//			grid.moveTabFirst();
//			keyEvent.preventDefault();
//			return;
//		}
//		
//		if(grid.moveTabColumns.length == 1){
//			/** 컬럼이 하나라면 */
//			if(keyEvent.shiftKey){
//				this.onKeyUp(keyEvent);	
//			}else{
//				this.onKeyDown(keyEvent);	
//			}
//			keyEvent.preventDefault();
//		}else if(grid.moveTabColumns.length == 2){
//			/** 컬럼이 두개라면 */
//			if(keyEvent.shiftKey){
//				this.reverseWalk(keyEvent);
//			}else{
//				this.walk(keyEvent);
//			}
//		}else{
//			/** 컬럼이 여러개라면 */
//			if(keyEvent.shiftKey){
//				// this.reverseWalk();
//			}else{
//				// this.walk();
//			}
//			this.onKeyTabOriginal(keyEvent);
//			return;
//		}
//  },
//  
//  /** 역방향 */
//  reverseWalk: function(keyEvent){
//  	// 1. (index값이 적은 컬럼이 존재한다면) 좌측으로 간다 (index 차이만큼 이동)
//  	// 2. (index값이 적은 컬럼이 없다면) 우측, 윗방향으로 간다 (index 차이만큼 이동)
//  	this.vehicle(keyEvent, this.reverseDirection());
//  },
//  
//  /** 정방향 */
//  walk: function(keyEvent){
//  	// 1. (index값이 큰 컬럼이 존재한다면) 우측으로 간다 (index 차이만큼 이동)
//  	// 2. (index값이 큰 컬럼이 없다면) 좌측, 아래방향으로 간다 (index 차이만큼 이동)
//  	this.vehicle(keyEvent, this.direction());
//  },
//  
//  /** 정방향 거리 */
//  direction: function(){
//  	var grid = this.view.ownerGrid;
//  	var columns = grid.moveTabColumns;
//  	var currentIndex;
//  	for(var i=0; i<columns.length; i++){
//  		if(this.column.id == columns[i].id){
//  			currentIndex = i;
//  		}
//  	}
//  	if(currentIndex == 0){
//  		var rightDistance = columns[1].getIndex() - columns[0].getIndex();
//  		return {right:rightDistance};
//  	}else{ /** currentIndex == 1 */ 
//  		var leftDistance = columns[1].getIndex() - columns[0].getIndex();
//  		return {bottom:1, left:leftDistance};
//  	}
//  },
//  
//  /** 역방향 거리 */
//  reverseDirection: function(){
//  	var grid = this.view.ownerGrid;
//  	var columns = grid.moveTabColumns;
//  	var currentIndex;
//  	for(var i=0; i<columns.length; i++){
//  		if(this.column.id == columns[i].id){
//  			currentIndex = i;
//  		}
//  	}
//  	if(currentIndex == 0){
//  		var rightDistance = columns[1].getIndex() - columns[0].getIndex();
//  		return {top:1, right:rightDistance};
//  	}else{ /** currentIndex == 1 */ 
//  		var leftDistance = columns[1].getIndex() - columns[0].getIndex();
//  		return {left:leftDistance};
//  	}
//  },
//  
//  /** 이동 */
//  vehicle: function(keyEvent, distance){
//  	/** LEFT */
//  	if(distance.left){
//  		while(distance.left != 0){
//  			distance.left -= 1;
//  			this.onKeyLeft(keyEvent);
//  		}
//  	}
//  	/** RIGHT */
//  	if(distance.right){
//  		while(distance.right != 0){
//  			distance.right -= 1;
//  			this.onKeyRight(keyEvent);
//  		}
//  	}
//  	/** TOP */
//  	if(distance.top){
//  		while(distance.top != 0){
//  		distance.top -= 1;
//  			this.onKeyUp(keyEvent);
//  		}
//  	}
//  	/** BOTTOM */
//  	if(distance.bottom){
//  		while(distance.bottom != 0){
//  		distance.bottom -= 1;
//  			this.onKeyDown(keyEvent);
//  		}
//  	}
//  },
//  
//  /** 탭이동 대상 컬럼 여부 */
//  isMoveTabColumn: function(column){
//  	var grid = this.view.ownerGrid;
//  	var columns = grid.moveTabColumns;
//  	if(!columns){
//  		grid.extractMoveTabColumns();
//  		columns = grid.moveTabColumns;
//  	}
//  	for(var i=0; i<columns.length; i++){
//  		if(columns[i].id == column.id){
//  			return true;
//  		}
//  	}
//  	return false;
//  }
//});
///** [7] 웹접근성 제거대상( [6]번 종속 ) : (그리드) 링크컬럼, 첨부파일컬럼 대상 탭이동 가능[TECHSUPP-2140] */
//Ext.define('Etna.override.moveTab.grid.Panel', {
//	override: 'Ext.grid.Panel',
//	onFocus: function(e){
//		console.log("using keyboard : onFocus");
//		this.callParent(arguments);
//		this.ownerGrid.extractMoveTabColumns = this.extractMoveTabColumns.bind(this);
//		this.ownerGrid.moveTabFirst = this.moveTabFirst.bind(this);
//		this.ownerGrid.extractMoveTabColumns();
//		this.ownerGrid.moveTabFirst();
//	},
//	/** MoveTab 끝 */
//	onFocusLeave: function(e){
//		this.callParent(arguments);
//		this.ownerGrid.useMoveTab = false;
//	},
//	extractMoveTabColumns: function(){
//		var grid = this.ownerGrid;
//		var columns = grid.columnManager.getColumns();
//		grid.moveTabColumns = [];
//		for(var i=0; i<columns.length; i++){
//			if(columns[i].tdCls == "link"){
//				grid.moveTabColumns.push(columns[i]);
//			}
//			if(columns[i].xtype == "etnaattachmentcolumn"){
//				grid.moveTabColumns.push(columns[i]);
//			}
//		}
//	},
//	/** MoveTab 시작 */
//	moveTabFirst: function(){
//		
//		if(this.view.up("etnagriduploader")){
//			return;
//		}
//		
//		var grid = this.ownerGrid;
//		grid.useMoveTab = true;
//		if(grid.selModel.selType != 'checkboxmodel'){
//			grid.selModel.select(0);
//		}
//		if(grid.moveTabColumns.length > 0){
//			var position = grid.selModel.navigationModel.position;
//			position.column = grid.moveTabColumns[0];
//			position.colIdx = grid.moveTabColumns[0].getIndex();
//			grid.selModel.navigationModel.setPosition(position); 	
//		}
//	}
//});
//
///** [8] 웹접근성 제거대상( [6]번 종속 ) : (그리드) 링크컬럼, 첨부파일컬럼 대상 탭이동 가능[TECHSUPP-2140]  */
//Ext.define('Etna.override.grid.plugin.Block', {
//	override : 'Etna.grid.plugin.Block',
//	render : function(renderInfo) {
//		var moveTabColumns = this.cmp.ownerGrid.moveTabColumns;
//		if(!moveTabColumns){
//			this.callParent(arguments);
//		}
//	}
//});
//
///** Left Menu 초기화 */
///** [10] 웹접근성 제거대상 [1] LEFT메뉴/탭바 CSS 오동작(1) : Left Menu 초기화[TECHSUPP-2140] */
//Ext.define('Etna.overrid.tree.Column', {
//	override: 'Ext.tree.Column',
//	initComponent: function() {
//		this.on("afterrender", function(e){
//			this.onAfterRender();
//		});
//		this.callParent(arguments);
//	},
//	onAfterRender: function(){
//		var mdileft = this.up("mdileft");
//		if(mdileft){
//			this.callForMdiLeft();
//		}
//	},
//	callForMdiLeft: function(){
//		var leftTreeView = this.getView();
//		var leftbody = leftTreeView.up().body;
//		leftbody.on("focusin", function(e){ 
//			var me = this.getView();
//			if(e.parentEvent.relatedTarget && !e.parentEvent.relatedTarget.classList.contains("x-grid-cell-treecolumn")){
//				var navModel = me.selModel.navigationModel;
//				var idx = 0;
//				me.selModel.select(idx);
//				me.selModel.navigationModel.position.rowIdx = idx;
//				me.selModel.navigationModel.setPosition(me.selModel.navigationModel.position);
//			}
//		}.bind(this));
//	}
//});
//
///** MDI탭바 초기화 */
///** 웹접근성 제거대상(성능/오동작위험)[1] LEFT메뉴/탭바 CSS 오동작(2) : MDI탭바 초기화[TECHSUPP-2140] */
//Ext.define('Etna.override.a11y2.tab.Bar', {
//	override: 'Ext.tab.Bar',
//	initComponent: function() {
//		this.on("afterrender", function(e){
//			this.onAfterRender();
//		});
//		this.callParent(arguments);
//	},
//	onAfterRender: function(){
//		var mdiviewport = this.up('mdiviewport');
//		if(mdiviewport){
//			this.callForMdiViewPort();
//		}
//	},
//	callForMdiViewPort: function(){
//		this.body.on("focusenter", function(e){
//			if(this.items && this.items.items && this.items.items[0]){
//				this.items.items[0].focus();
//			}
//		}.bind(this));
//	}
//});
//웹접근성 관련 롤백 구간6 끝 
/**********************************************************************/
/************** 2021.03.23 추가반영 *************************************/
/**********************************************************************/
/** [2021.03.23 항목1] 탭바 닫기버튼 */
Ext.define('Etna.override.a11y3.tab.Bar', {
	override: 'Ext.tab.Bar',
	afterTabRender: function(comp, e){
		if(comp.el.dom && comp.el.dom.querySelector("[data-ref=closeEl]")){
			comp.el.onBefore("focus", function(e){ 
				comp.el.dom.querySelector("[data-ref=closeEl]").innerText = "";
			});
			comp.el.dom.querySelector("[data-ref=closeEl]").innerText = "";
		}
		this.callParent(arguments);
	},
	findCloseEl: function(e){
		console.log("findCloseEl");
		var closeBtn = e.target.querySelector("span.x-tab-close-btn");
		var closeBtnText = "닫기";
		if(closeBtn){
			closeBtn.setAttribute("role", "button");
			closeBtn.innerText = closeBtnText;
			closeBtn.setAttribute("tabindex", 0);
		}
		this.callParent(arguments);
	}
});

/** 웹접근성 제거대상(성능/오동작위험)[1] LEFT메뉴/탭바 CSS 오동작(3) : [2021.03.23 항목2] Left Menu 초기화[TECHSUPP-2141] */
/** [2021.03.23 항목2] Left Menu 초기화 */
//2022.04.28 Hoon 웹접근성 관련 롤백 구간7
//Ext.define('Etna.overrid2.tree.Column', {
//	override: 'Ext.tree.Column',
//	callForMdiLeft: function(){
//		var leftTreeView = this.getView();
//		var leftbody = leftTreeView.up().body;
//		leftbody.on("focusin", function(e){ 
//			var me = this.getView();
//			if(e.parentEvent.relatedTarget && (e.parentEvent.relatedTarget.classList && !e.parentEvent.relatedTarget.classList.contains("x-grid-cell-treecolumn"))){
//				var navModel = me.selModel.navigationModel;
//				var idx = 0;
//				me.selModel.select(idx);
//				me.selModel.navigationModel.position.rowIdx = idx;
//				me.selModel.navigationModel.setPosition(me.selModel.navigationModel.position);
//			}
//			
//			var me = this.getView();
//			var tds = me.el.dom.querySelectorAll("td:not([description])");
//			for(var i=0; i<tds.length; i++){
//				var hTag = tds[i].querySelector("span").firstElementChild;
//				var titleText = hTag.innerText + " 탭으로 이동해야 선택 ";
//				tds[i].setAttribute("tabindex", "0");
//				tds[i].setAttribute("title", titleText);
//			}
//		}.bind(this));
//	}
//});
//웹접근성 관련 롤백 구간7 끝 
/** [2021.03.23 항목1,2와 연관] 레프트 메뉴에서 탭바로 넘어갈때, 첫번째 탭바로 포커스 */
Ext.define('Mdi.view.override3.mdi.LeftViewController', {
	override: 'Mdi.view.mdi.LeftViewController',
	nextFocusOutElmentSelector: '.x-tab-mdi-tabbar',
	a11yTabkeyDownHandler: function(e){
		/** 마지막 로우(포커스가 밖으로 나가야 됨) */
		if(this.view.selModel.store.data.items.length-1 == this.view.selModel.navigationModel.position.rowIdx){
			var next = document.querySelector(this.nextFocusOutElmentSelector);
			if(next){
				e.preventDefault();
				e.stopPropagation();
				next.focus();
			}
		} else{
			e.preventDefault();
			e.stopPropagation();
			var navModel = this.view.selModel.navigationModel;
			var idx = navModel.position.rowIdx+1;
			this.view.selModel.select(idx);
			this.view.selModel.navigationModel.position.rowIdx = idx;
			this.view.selModel.navigationModel.setPosition(this.view.selModel.navigationModel.position);
		}
	}
});

/** [2021.03.23 항목5] 다운로드 / 삭제 / 상태 */
/** [9] 웹접근성 제거대상(첨부파일 종속) : [2021.03.23 항목5] 다운로드 / 삭제[TECHSUPP-2141] */
//2022.04.28 Hoon 웹접근성 관련 롤백 구간8
//Ext.define('Etna.override.a11y4.upload.StoreBasedUploader', {
//	override: 'Etna.upload.StoreBasedUploader',
//	onKeyHandler: function(e){ 
//		this.callParent(arguments);
//		this.addDescription();
//	},
//	addDescription: function(){
//		this.toDownloadCell();
//		this.toCheckboxCell();
//		this.toStatusCell();
//		
//	},
//	toDownloadCell: function(){
//		var downloadCells = this.body.el.dom.querySelectorAll(".x-etna-uploader-file-default:not([description])");;
//		var titleText = "다운로드는 alt enter";
//		for(var i=0; i<downloadCells.length; i++){
//			var cell = downloadCells[i];
//			var cellText = cell.innerText;
//			if(cell){
//				var td = cell.parentElement.parentElement;
//				td.setAttribute("tabindex", 0);
//				td.setAttribute("title", cellText + titleText);
//				cell.setAttribute("description", "true");
//			}
//		}
//	},
//	toCheckboxCell: function(){
//		var removeCells = this.body.el.dom.querySelectorAll(".x-grid-cell-row-checker:not([title])");
//		var titleText = "삭제 컬럼. 엔터 시 삭제";
//		for(var i=0; i<removeCells.length; i++){
//			var cell = removeCells[i];
//			if(cell){
//				cell.setAttribute("tabindex", 0);
//				cell.setAttribute("title", titleText);
//			}
//		}
//	},
//	toStatusCell: function(){
//		var uploadableCells = this.body.el.dom.querySelectorAll(".x-etna-grid-uploader-status-local:not([title])");
//		var uploadableText = "업로드 가능 상태";
//		for(var i=0; i<uploadableCells.length; i++){
//			var upCell = uploadableCells[i].parentElement.parentElement;
//			if(upCell){
//				upCell.setAttribute("tabindex", 0);
//				upCell.setAttribute("title", uploadableText);
//			}
//		}
//		var downloadableCells = this.body.el.dom.querySelectorAll(".x-etna-grid-uploader-status-remote:not([title])");
//		var downloadableText = "다운로드 가능 상태";
//		for(var i=0; i<downloadableCells.length; i++){
//			var downCell = downloadableCells[i].parentElement.parentElement;
//			if(downCell){
//				downCell.setAttribute("tabindex", 0);
//				downCell.setAttribute("title", downloadableText);
//			}
//		}
//	}
//});
//
///** [2021.03.23 항목6] 그리드 체크박스 리더기에서 읽기(role="checkbox") */
///** [10] 웹접근성 제거대상(성능/오동작위험) : [2021.03.23 항목6] 그리드 체크박스(SelectionModel) : 연관된 이슈로 스페이스키를 통한 선택/해제 음성 안내[TECHSUPP-2141] */
//Ext.override(Ext.selection.CheckboxModel, { 
//	renderer: function(value, metaData, record, rowIndex, colIndex, store, view) { 
//		var columnComp = this._getTargetColumnComp(view, record); 
//		var selectionText = this._getTextFormColumnAndRecord(columnComp, record); 
//		return '<div class="' + Ext.baseCSSPrefix + 'grid-row-checker" role="checkbox" aria-label="' + selectionText + '">&#160;</div>'; 
//	} 
//});
//
///** [2021.03.23 항목6] 그리드 체크박스(SelectionModel) : 연관된 이슈로 스페이스키를 통한 선택/해제 음성 안내 */
///** [10] 웹접근성 제거대상(성능/오동작위험) : [2021.03.23 항목6] 그리드 체크박스(SelectionModel) : 연관된 이슈로 스페이스키를 통한 선택/해제 음성 안내[TECHSUPP-2141] */
//Ext.define('Etna.override.selmodel.check.GridView', {
//	override: 'Ext.grid.Panel',
//	onRender: function() {
//		this.callParent();
//		Etna.onDone(function(){
//			var grids = this.items.items;
//			if(grids && grids[0] && grids[0].xtype == "grid" && grids[0].view){
//				var selModelGridView = grids[0].view;
//				selModelGridView.el.on("focusenter", function(e){ 
//					this.focusInStart = false;
//				});
//				selModelGridView.el.on("focusin", function(e){ 
//					if(this.focusInStart == false){
//						this.focusInStart = true;
//						return;
//					}
//					var checkEl = e.target.querySelector("div.x-grid-row-checker");
//					if(checkEl){
//						var disableCheckers = this.el.dom.querySelectorAll("div.x-grid-row-checker");
//						for(var i=0; i<disableCheckers.length; i++){
//							if(checkEl == disableCheckers[i]){
//								setTimeout(function(disableChecker){
//									disableChecker.setAttribute("aria-checked", true);	
//								}.bind(this, disableCheckers[i]), 50);
//							}else if(disableCheckers[i].getAttribute("aria-label") && disableCheckers[i].getAttribute("aria-label").indexOf("체크됨") >= 0){
//								disableCheckers[i].setAttribute("aria-checked", true);
//							}else{
//								//setTimeout(function(disableChecker){
//									disableCheckers[i].setAttribute("aria-checked", false);
//								//}.bind(this, disableCheckers[i]), 1);
//							}
//						}
//					}
//				});
//				selModelGridView.el.on("focusleave", function(e){ 
//					var checkEl = e.target.querySelector("div.x-grid-row-checker");
//					if(checkEl){
//						var checkLabel = checkEl.getAttribute("aria-label");
//						if(checkLabel.indexOf("체크됨") >= 0){
//							checkEl.setAttribute("aria-checked", true);
//						}else{
//							checkEl.setAttribute("aria-checked", false);
//						}
//					}
//				});
//			}
//		}.bind(this));
//	}
//});
//
///** 20220329-001 임시코드 : TabPanel 포커스 안들어 가는 현상 시작*/
//Ext.define('Etna.override.tab.Panel', {
//    override : 'Ext.tab.Panel',
//    initComponent: function() {
//        this.callParent(arguments);
//        setInterval(this.restoreFocus.bind(this), 1000);
//    },
//    restoreFocus: function(){
//        var hasRest
//        var tabItems = this.tabBar.items.items;
//        for(var i=0; i<tabItems.length; i++){
//            if(tabItems[i].el && tabItems[i].el.dom.tabIndex != -1){
//                return;
//            }
//        }
//        if((i > 0) && (this.tabBar.items.items[0].el)){
//            this.tabBar.items.items[0].el.dom.tabIndex = 0;
//        }
//    }
//});
//Ext.define('Etna.override.focusable.tab.Bar', {
//	override: 'Ext.tab.Bar',
//	onActiveTab: function(e){this.callParent(arguments);
//		this.findNonInputFocusOnActiveTab(e);	
//	},
//	findNonInputFocusOnActiveTab: function(e){
//		var tabPanel = this.ownerCt;
//		var currentTarget = e.target, parent = currentTarget.parentElement;
//		/** Is Last TabBar */ 
//		if((e.keyCode == 9 && !e.shiftKey) && (/** TabBar */e.target.tagName.toLowerCase() == 'a') && (parent.children[parent.children.length-1] == currentTarget)){
//			if(tabPanel.activeTab){ 
//				var allEl = tabPanel.activeTab.query("tab, textfield, datefield, textarea, checkbox, radio, combo, button, fieldcontainer");
//				var focusableEl = tabPanel.activeTab.query("button, fieldcontainer");
//				if(focusableEl && focusableEl.length > 0 && (allEl.length == focusableEl.length)){ 
//					focusableEl[0].focus();
//					e.preventDefault(); 							
//					e.stopPropagation(); 		
//				}		
//			}
//		}
//	}
//});
/** 20220329-001 임시코드 : TabPanel 포커스 안들어 가는 현상 끝*/
//웹접근성 관련 롤백 구간8 끝 

/********** 2025.02.26 고아라 *********/
/** 메시지 기록 페이지 노출 취약점 조치(로컬 스토리지 다국어 메시지 적재 기능 비활성화) */
/** (1-1) Message Not Found 시, 서버요청(byKeys.do) 하지 않음 */
Ext.define("MessageSource.override2.i18n.Provider", {
	override: "Etna.i18n.Provider",
	loadValues: function(values, locale) {
		var result = {};
		for(var key in values) {
			result[values[key]] = values[key];
		}
		return {
			noneLocalStorage : true,
			messages : result
		}
	}
});

/** (1-2) 로컬 스토리지 저장 여부 */
Ext.define("MessageSource.override2.i18n.Storage", {
	override: "Etna.i18n.Storage",
	set: function(values, locale) {
		var memoryStorage = this.storage;
		if(!values.noneLocalStorage){
			this.callParent(arguments);
		}else{
			values = values.messages
			for(var key in values) { 
				memoryStorage.setItem(locale+"."+key, values[key]); 
			}
		}
	}
});