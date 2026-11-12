/*
This file is part of Ext JS 4.2

Copyright (c) 2011-2013 Sencha Inc

Contact:  http://www.sencha.com/contact

Commercial Usage
Licensees holding valid commercial licenses may use this file in accordance with the Commercial
Software License Agreement provided with the Software or, alternatively, in accordance with the
terms contained in a written agreement between you and Sencha.

If you are unsure which license is appropriate for your use, please contact the sales department
at http://www.sencha.com/contact.

Build date: 2013-05-16 14:36:50 (f9be68accb407158ba2b1be2c226a6ce1f649314)
 */
/**
 * Korean Translations By nicetip 05 September 2007 Modify by techbug / 25
 * February 2008
 */
Ext.onReady(function()
{

	if (Ext.Date)
	{
		Ext.Date.monthNames = [ "1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월" ];
		Ext.Date.dayNames = [ "일", "월", "화", "수", "목", "금", "토" ];
		Ext.Date.defaultFormat = 'Y/m/d';
		Ext.Date.defaultTimeFormat = 'A g:i';
		Ext.apply(Ext.Date.formatCodes, {
			a : "(this.getHours() < 12 ? '오전' : '오후')",
			A : "(this.getHours() < 12 ? '오전' : '오후')"
		});
		Ext.Date.patterns = {
			'DateTime' : Ext.Date.defaultFormat + " " + Ext.Date.defaultTimeFormat
		}
	}

	if (Ext.util && Ext.util.Format)
	{
		Ext.apply(Ext.util.Format, {
			thousandSeparator : ',',
			decimalSeparator : '.',
			currencySign : '\u20a9',
			// Korean Won
			dateFormat : 'Y/m/d',
			numberWord : (function()
					{
				var baseNames =  ["천", "백", "십", ""];
			    var levelNames = ["", "만", "억", "조", 
			                      "경", "해", "자", "양", 
			                      "구", "간", "정", "재", 
			                      "극", "항하사", "아승기", "나유타", 
			                      "불가사의", "무량대수"];
			    var decimals = ["영", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"];
			    var delimChar = " ";
			    var result = "";
				return function(value)
				{
					value = String(value);
					var postFix = '', pointIndex = value.indexOf('.'), signIndex = value.indexOf('-');
					if(pointIndex > -1){
						var fraction = value.substr(pointIndex + 1);
						value = value.substr(0, pointIndex);
						if(fraction){
							postFix = ".";
						}
						for(var i=0 ; i < fraction.length ; i++){
							postFix += decimals[Number(fraction.charAt(i))];
						}
					}
					
					//음수 체크 부분 추가
					if(signIndex > -1){
						value = value.substring(++signIndex, value.length);
						result = "-";
					}else{
						result = "";
					}
					
					var length = value.length,
						level = parseInt(length / baseNames.length),
					    start = 0,
					    end = length % baseNames.length; // 0, 1, 2, 3
				    /* start validation */
				    if ( length > 69 ) {
				        throw "too long number : " + num ;
				    }
				    if ( isNaN(value) ) {
				        throw "not a number form : " + num ;
				    }
				    if ( ! isFinite(value) ) {
				        throw "not finite : " + num ;
				    }
				    /* end validation */
				    
				    if ( end == 0) { // in case the length of num is => 0, 4, 8, 12, ...
				        end = Math.min(length, baseNames.length) ;
				        level --;
				    } else {
				        for( var k = 0 ; k < baseNames.length-end; k++) {
				        	value = "0" + value;
				        }
				        end = baseNames.length;
				    }
				    
				    while ( start < length ) {
				        var partial = value.substring(start, end);
				        var unitStr = "";        
				        
				        for( var i = 0 ; i < partial.length ; i++) {
				        	var ch = partial.charAt(i);
				        	if ( ch != "0") {
			                    unitStr += decimals [ parseInt(ch)] + baseNames[i];
			                }
				        }
				        
				        if ( unitStr.length > 0 ) {
				        	result += unitStr + levelNames[level] + delimChar ;
				        }
				        level--;
				        start = end;
				        end += baseNames.length;
				    }
				    // 0에 대한 한글표현 추가
				    if(result.length == 0){
				    	result = decimals[0];
				    }
				    return Ext.String.trim(result) + postFix;
				};
			})()
		});
	}
});

Ext.define("Ext.locale.ko.view.View", {
	override : "Ext.view.View",
	emptyText : ""
});

Ext.define("Ext.locale.ko.grid.plugin.DragDrop", {
	override : "Ext.grid.plugin.DragDrop",
	dragText : "{0} 개가 선택되었습니다."
});

Ext.define("Ext.locale.ko.tab.Tab", {
	override : "Ext.tab.Tab",
	closeText : "닫기"
});

Ext.define("Ext.locale.ko.form.field.Base", {
	override : "Ext.form.field.Base",
	invalidText : "올바른 값이 아닙니다."
});

// changing the msg text below will affect the LoadMask
Ext.define("Ext.locale.ko.view.AbstractView", {
	override : "Ext.view.AbstractView",
	loadingText : "로딩중..."
});

// http://alm.emro.co.kr/browse/TECHSUPP-327 로딩메세지 한글화
Ext.define("Ext.local.ko.LoadMask",{
	override : 'Ext.LoadMask',
	 msg: "로딩중..."
});

Ext.define("Ext.locale.ko.picker.Date", {
	override : "Ext.picker.Date",
	todayText : "오늘",
	minText : "최소 날짜범위를 넘었습니다.",
	maxText : "최대 날짜범위를 넘었습니다.",
	disabledDaysText : "",
	disabledDatesText : "",
	nextText : '다음달(컨트롤키+오른쪽 화살표)',
	prevText : '이전달 (컨트롤키+왼족 화살표)',
	monthYearText : '월을 선택해주세요. (컨트롤키+위/아래 화살표)',
	todayTip : "{0} (스페이스바)",
	format : "Y/m/d",
	startDay : 0
});

Ext.define("Ext.locale.ko.picker.Month", {
	override : "Ext.picker.Month",
	okText : "확인",
	cancelText : "취소"
});

Ext.define("Ext.locale.ko.toolbar.Paging", {
	override : "Ext.PagingToolbar",
	beforePageText : "페이지",
	afterPageText : "/ {0}",
	firstText : "첫 페이지",
	prevText : "이전 페이지",
	nextText : "다음 페이지",
	lastText : "마지막 페이지",
	refreshText : "새로고침",
	displayMsg : "전체 {2} 중 {0} - {1}",
	emptyMsg : '표시할 데이터가 없습니다.'
});

Ext.define("Ext.locale.ko.form.field.Text", {
	override : "Ext.form.field.Text",
	minLengthText : "최소길이는 {0}입니다.",
	maxLengthText : "최대길이는 {0}입니다.",
	blankText : "값을 입력해주세요.",
	regexText : "",
	emptyText : null
});

Ext.define("Ext.locale.ko.form.field.Number", {
	override : "Ext.form.field.Number",
	minText : "최소값은 {0}입니다.",
	maxText : "최대값은 {0}입니다.",
	nanText : "{0}는 올바른 숫자가 아닙니다.",
	negativeText: '음수값이 될수 없습니다.'
});

Ext.define("Ext.locale.ko.form.field.Date", {
	override : "Ext.form.field.Date",
	disabledDaysText : "비활성",
	disabledDatesText : "비활성",
	minText : "{0}일 이후여야 합니다.",
	maxText : "{0}일 이전이어야 합니다.",
	invalidText : "{0}는 올바른 날짜형식이 아닙니다. - 다음과 같은 형식이어야 합니다. {1}",
	format : "Y/m/d"
});

Ext.define("Ext.locale.ko.form.field.ComboBox", {
	override : "Ext.form.field.ComboBox",
	valueNotFoundText : undefined
}, function()
{
	Ext.apply(Ext.form.field.ComboBox.prototype.defaultListConfig, {
		loadingText : "로딩중..."
	});
});

Ext.define("Ext.locale.ko.form.field.VTypes", {
	override : "Ext.form.field.VTypes",
	emailText : '이메일 주소 형식에 맞게 입력해야합니다. (예: "redacted@example.invalid")',
	urlText : 'URL 형식에 맞게 입력해야합니다. (예: "http:/' + '/www.example.com")',
	alphaText : '영문, 밑줄(_)만 입력할 수 있습니다.',
	alphanumText : '영문, 숫자, 밑줄(_)만 입력할 수 있습니다.'
});

Ext.define("Ext.locale.ko.form.field.HtmlEditor", {
	override : "Ext.form.field.HtmlEditor",
	createLinkText : 'URL을 입력해주세요:'
}, function()
{
	Ext.apply(Ext.form.field.HtmlEditor.prototype, {
		buttonTips : {
			bold : {
				title : '굵게 (Ctrl+B)',
				text : '선택한 텍스트를 굵게 표시합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			italic : {
				title : '기울임꼴 (Ctrl+I)',
				text : '선택한 텍스트를 기울임꼴로 표시합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			underline : {
				title : '밑줄 (Ctrl+U)',
				text : '선택한 텍스트에 밑줄을 표시합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			increasefontsize : {
				title : '글꼴크기 늘림',
				text : '글꼴 크기를 크게 합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			decreasefontsize : {
				title : '글꼴크기 줄임',
				text : '글꼴 크기를 작게 합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			backcolor : {
				title : '텍스트 강조 색',
				text : '선택한 텍스트의 배경색을 변경합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			forecolor : {
				title : '글꼴색',
				text : '선택한 텍스트의 색을 변경합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			justifyleft : {
				title : '텍스트 왼쪽 맞춤',
				text : '왼쪽에 텍스트를 맞춥니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			justifycenter : {
				title : '가운데 맞춤',
				text : '가운데에 텍스트를 맞춥니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			justifyright : {
				title : '텍스트 오른쪽 맞춤',
				text : '오른쪽에 텍스트를 맞춥니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			insertunorderedlist : {
				title : '글머리 기호',
				text : '글머리 기호 목록을 시작합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			insertorderedlist : {
				title : '번호 매기기',
				text : '번호 매기기 목록을 시작합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			createlink : {
				title : '하이퍼링크',
				text : '선택한 텍스트에 하이퍼링크를 만듭니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			},
			sourceedit : {
				title : '소스편집',
				text : '소스편집 모드로 변환합니다.',
				cls : Ext.baseCSSPrefix + 'html-editor-tip'
			}
		}
	});
});

Ext.define("Ext.locale.ko.grid.header.Container", {
	override : "Ext.grid.header.Container",
	sortAscText : "오름차순 정렬",
	sortDescText : "내림차순 정렬",
	lockText : "칼럼 잠금",
	unlockText : "칼럼 잠금해제",
	columnsText : "칼럼 목록"
});

Ext.define("Ext.locale.ko.grid.GroupingFeature", {
	override : "Ext.grid.GroupingFeature",
	emptyGroupText : '(None)',
	groupByText : '현재 필드로 그룹핑합니다.',
	showGroupsText : '그룹으로 보여주기'

});

Ext.define("Ext.locale.ko.grid.PropertyColumnModel", {
	override : "Ext.grid.PropertyColumnModel",
	nameText : "항목",
	valueText : "값",
	dateFormat : "Y/m/d"
});

Ext.define("Ext.locale.ko.window.MessageBox", {
	override : "Ext.window.MessageBox",
	buttonText : {
		ok : "확인",
		cancel : "취소",
		yes : "예",
		no : "아니오"
	}
});

Ext.define("Ext.locale.ko.form.field.Time", {
	override : "Ext.form.field.Time",
	format : 'A g:i'
});

// etnajs 에서 추가된 내용은 여기에 설정
Ext.onReady(function(){
	Ext.define("Ext.locale.en.view.BoundList", {
		override : "Ext.view.BoundList",
		selectAllText : '전체 선택'
	});

	Ext.define('Ext.locale.en.grid.header.Container', {
		override : "Ext.grid.header.Container",
		sortInitializeText : '정렬 초기화'
	});

	Ext.define('Etna.locale.en.grid.plugin.MultiSort', {
		override : 'Etna.grid.plugin.MultiSort',
		
		multipleSortAscText : '다중 오름차순 정렬',
		
		multipleSortDescText : '다중 내림차순 정렬'
	});
});

/**
* 한국전력 다국어 처리
*/
Ext.define('Etna.locale.ko.LoadMask', {
	override : 'Ext.LoadMask',
	msg : 'Data 로딩중...'
});

Ext.define("Etna.locale.ko.view.AbstractView", {
	override : "Ext.view.AbstractView",
	loadingText : 'Data 로딩중...'
});

Ext.define("Etna.locale.ko.form.field.ComboBox", {
	override : "Ext.form.field.ComboBox"
}, function() {
	Ext.apply(Ext.form.field.ComboBox.prototype.defaultListConfig, {
		loadingText : 'Data 로딩중...'
	});
});

Ext.define('Mdi.locale.ko.view.mdi.ViewportViewController', {
    override: 'Mdi.view.mdi.ViewportViewController',
    
    onTabpanelRender : function(component) {
    	var me = this;
    	me.callParent(arguments);
    	
    	if(component.loadMask) {
    		component.loadMask.msg = '화면 로딩중...';
    	}
    }
});

/**
* plupload 다국어 처리
*/
plupload.addI18n({"Stop Upload":"업로드 중지","Upload URL might be wrong or doesn't exist.":"업로드할 URL이 존재하지 않습니다",tb:"",Size:"크기",Close:"닫기","Init error.":"초기화 오류","Add files to the upload queue and click the start button.":"파일을 업로드 큐에 추가하여 시작 버튼을 클릭하십시오.",Filename:"파일 이름","Image format either wrong or not supported.":"Image format either wrong or not supported.",Status:"상태","HTTP Error.":"HTTP 오류","Start Upload":"업로드",mb:"",kb:"","Duplicate file error.":"","File size error.":"첨부 가능한 파일 사이즈를 초과하였습니다.","N/A":"N/A",gb:"","Error: Invalid file extension:":"오류 : 확장자가 허용되지 않습니다 :","Select files":"파일 선택","%s already present in the queue.":"","File: %s":"파일 % s",b:"","Uploaded %d/%d files":"업로드 중 %d / %d 파일","Upload element accepts only %d file(s) at a time. Extra files were stripped.":"업로드 가능한 파일의 수는 %d입니다. 불필요한 파일은 삭제되었습니다","%d files queued":"%d 파일이 추가되었습니다","File: %s, size: %d, max file size: %d":"","Drag files here.":"여기에 파일을 드래그","Runtime ran out of available memory.":"Runtime ran out of available memory.","File count error.":"이미지 : 오류","File extension error.":"허용되지 않는 확장자 입니다.","Error: File too large:":"오류 : 크기가 너무 큽니다","Add Files":"파일 추가","File minimum size error.":"첨부가능한 최소 사이즈보다 작습니다.","Total File size error.":"첨부가능한 최대 사이즈를 초과하였습니다.","File count limit":"첨부 가능한 최대 파일 수를 초과하였습니다."});