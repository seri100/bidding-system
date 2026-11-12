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