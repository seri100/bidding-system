/**
 * Barebones iframe implementation. For serious iframe work, see the
 * ManagedIFrame extension
 * (http://www.sencha.com/forum/showthread.php?71961).
 */
var isForeign = false;

Ext.define('Mdi.ux.IFrame', {
    extend: Ext.Component,
    alias: 'widget.mdiiframe',
    loadMask: 'Loading...',
    src: 'about:blank',
    renderTpl: [
    	//프레임 제목 미제공 pdf#42
        '<iframe src="{src}" id="{id}-iframeEl" data-ref="iframeEl" name="{frameName}" width="100%" height="100%" frameborder="0" title ="메인화면"></iframe>'
    ],
    childEls: [
        'iframeEl'
    ],
    initComponent: function() {
        this.callParent();
        this.frameName = this.frameName || this.id + '-frame';
    },
    initEvents: function() {
        var me = this;
        me.callParent();
        me.iframeEl.on('load', me.onLoad, me);
    },
    initRenderData: function() {
        return Ext.apply(this.callParent(), {
            src: this.src,
            frameName: this.frameName
        });
    },
    getBody: function() {
        var doc = this.getDoc();
        return doc.body || doc.documentElement;
    },
    getDoc: function() {
        try {
            return this.getWin().document;
        } catch (ex) {
            return null;
        }
    },
    getWin: function() {
        var me = this,
            name = me.frameName,
            win = Ext.isIE ? me.iframeEl.dom.contentWindow : window.frames[name];
        return win;
    },
    getFrame: function() {
        var me = this;
        return me.iframeEl.dom;
    },
    beforeDestroy: function() {
        this.cleanupListeners(true);
        this.callParent();
    },
    cleanupListeners: function(destroying) {
        var doc, prop;
        if (this.rendered) {
            try {
                doc = this.getDoc();
                if (doc) {
                    Ext.get(doc).un(this._docListeners);
                    if (destroying) {
                        for (prop in doc) {
                            if (doc.hasOwnProperty && doc.hasOwnProperty(prop)) {
                                delete doc[prop];
                            }
                        }
                    }
                }
            } catch (e) {}
        }
    },
    onLoad: function() {
        var me = this,
            doc = me.getDoc(),
            fn = me.onRelayedEvent;
        if (doc) {
            try {
                // These events need to be relayed from the inner document (where they stop
                // bubbling) up to the outer document. This has to be done at the DOM level so
                // the event reaches listeners on elements like the document body. The effected
                // mechanisms that depend on this bubbling behavior are listed to the right
                // of the event.
                Ext.get(doc).on(me._docListeners = {
                    mousedown: fn,
                    // menu dismisal (MenuManager) and Window onMouseDown (toFront)
                    mousemove: fn,
                    // window resize drag detection
                    mouseup: fn,
                    // window resize termination
                    click: fn,
                    // not sure, but just to be safe
                    dblclick: fn,
                    // not sure again
                    scope: me
                });
            } catch (e) {}
            // cannot do this xss
            // We need to be sure we remove all our events from the iframe on unload or we're going to LEAK!
            Ext.get(this.getWin()).on('beforeunload', me.cleanupListeners, me);
            this.el.unmask();
            this.fireEvent('load', this);
        } else if (me.src) {
            this.el.unmask();
            this.fireEvent('error', this);
        }
    },
    onRelayedEvent: function(event) {
        // relay event from the iframe's document to the document that owns the iframe...
        var iframeEl = this.iframeEl,
            // Get the left-based iframe position
            iframeXY = iframeEl.getTrueXY(),
            originalEventXY = event.getXY(),
            // Get the left-based XY position.
            // This is because the consumer of the injected event will
            // perform its own RTL normalization.
            eventXY = event.getTrueXY();
        // the event from the inner document has XY relative to that document's origin,
        // so adjust it to use the origin of the iframe in the outer document:
        event.xy = [
            iframeXY[0] + eventXY[0],
            iframeXY[1] + eventXY[1]
        ];
        event.injectEvent(iframeEl);
        // blame the iframe for the event...
        event.xy = originalEventXY;
    },
    // restore the original XY (just for safety)
    load: function(src) {
        var me = this,
            text = me.loadMask,
            frame = me.getFrame();
        if (me.fireEvent('beforeload', me, src) !== false) {
            if (text && me.el) {
                me.el.mask(text);
            }
            frame.src = me.src = (src || me.src);
        }
    }
});

/*
 * File: app/controller/Manager.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.controller.Manager', {
    extend: Ext.Base,
    alternateClassName: [
        'MdiManager'
    ],
    singleton: true,
    mdiTab: null,
    mdiTabOverflow : 7,
    addView: function(className, config, requireClasses, callback) {
        var me = this,
            mdiTab = me.mdiTab;
        if (!className) {
            return;
        }
        if (me.isMdiTabOverflow()) {
            me.mdiTabOverflowHandler.apply(me, arguments);
            return;
        }
        if (mdiTab.addingViews[className]) {
            return;
        }
        mdiTab.addingViews[className] = true;
        config = config || {};
        config.mdiConfig = Ext.clone(config);
        if (me.mdiDisabled) {
            me.addViewToIFrame(className, config, requireClasses, callback);
        } else {
            me.addViewToTab(className, config, requireClasses, callback);
        }
        me.hideSpMain();
    },
    addViewToTab: function(className, config, requireClasses, callback) {
        var me = this,
            mdiTab = me.mdiTab,
            adding = false,
            activatedTab;
        config.classpath = className;
        config.requireClasses = requireClasses;
        var adder = Ext.Function.createDelayed(function() {
                var view;
                Ext.suspendLayouts();
                if (Ext.ClassManager.get(className).prototype.isWindow) {
                    view = Ext.create(className, Ext.applyIf(config, mdiTab.defaults));
                    view.on('beforeclose', function(c) {
                        c.destroy();
                    });
                    view.on('afterlayout', hider, me, {
                        single: true
                    });
                    view = mdiTab.add(view);
                    view.show();
                    mdiTab.setActiveTab(view);
                    view.tab.show();
                } else {
                    view = mdiTab.add(me.processMdiTabViewConfig(className, config));
                    view.on('afterlayout', function() {
//                        Ext.suspendLayouts();
                        hider();
                        var clearIntervalId = Ext.interval(function() {
                                if (Etna.data.Manager.count > 0 || Etna.data.Manager.isBindScheduled) {
                                    return;
                                }
//                                Ext.resumeLayouts(true);
                                clearInterval(clearIntervalId);
                            }, 100);
                    }, me, {
                        single: true
                    });
                    mdiTab.setActiveTab(view);
                }
                Ext.resumeLayouts(true);
                delete mdiTab.addingViews[className];
                if (Ext.isFunction(callback)) {
                    callback();
                }
            }, 1),
            hider = function() {
                if (mdiTab.loadMask && mdiTab.loadMask.isVisible()) {
                    mdiTab.setLoading(false);
                }
            };
        if ((activatedTab = mdiTab.getActiveTab())) {
            activatedTab.hide();
        }
        mdiTab.setLoading(true);
        if (requireClasses) {
            Ext.require(requireClasses, function() {
                Etna.onDone(function() {
                    Ext.require(className, adder);
                });
            });
        } else {
            Ext.require(className, adder);
        }
        Ext.defer(hider, 5000);
    },
    addViewToIFrame: function(className, config, requireClasses, callback) {
        var me = this;
        var url = me.buildIFrameUrl(className, config, requireClasses);
        me.mdiTab.setActiveTab(me.mdiIFrame);
        me.mdiIFrame.load(url);
        if (Ext.isFunction(callback)) {
            callback();
        }
    },
    addViews: function(configurations, callback) {
        var me = this,
            mdiTab = me.mdiTab,
            overflow, length;
        if (!configurations || configurations.length === 0) {
            return;
        }
        configurations = Ext.Array.filter(configurations, function(configuration) {
            var className = configuration.className || configuration.classpath;
            if (mdiTab.addingViews[className]) {
                return false;
            }
            mdiTab.addingViews[className] = true;
            return true;
        });
        if ((overflow = me.isMdiTabOverflow(configurations.length))) {
        	Etna.Message.alert(Ext.String.format("탭 생성 개수는 {0}개로 한정되어 있습니다.", me.mdiTabOverflow));
            length = configurations.length;
            configurations = Ext.Array.slice(configurations, 0, length - overflow);
        }
        if (configurations.length > 0) {
            me.addViewsToTab(configurations, callback);
        }
    },
    addViewsToTab: function(configurations, callback) {
        var me = this,
            mdiTab = me.mdiTab,
            items = [],
            requires = [],
            activatedTab;
        var adder = Ext.Function.createDelayed(function() {
                Ext.suspendLayouts();
                var views = mdiTab.add(items),
                    activeTab;
                Ext.Array.each(views, function(view) {
                    if (Ext.ClassManager.get(view.$className).prototype.isWindow) {
                        view.on('beforeclose', function(c) {
                            c.destroy();
                        });
                        view.show();
                        view.tab.show();
                    }
                    if (view.activeTab) {
                        activeTab = view;
                    }
                });
                if (!activeTab) {
                    activeTab = views[views.length - 1];
                }
                activeTab.on('afterlayout', hider, me, {
                    single: true
                });
                mdiTab.setActiveTab(activeTab);
                Ext.Array.each(configurations, function(configuration) {
                    var className = configuration.className || configuration.classpath;
                    delete mdiTab.addingViews[className];
                });
                Ext.resumeLayouts(true);
                if (Ext.isFunction(callback)) {
                    callback();
                }
            }, 1),
            hider = function() {
                if (mdiTab.loadMask && mdiTab.loadMask.isVisible()) {
                    mdiTab.setLoading(false);
                }
            };
        if ((activatedTab = mdiTab.getActiveTab())) {
            activatedTab.hide();
        }
        mdiTab.setLoading(true);
        Ext.Array.each(configurations, function(configuration, index) {
            var config,
                className = configuration.className || configuration.classpath,
                requireClasses;
            config = me.processMdiTabViewConfig(className, configuration);
            items.push(config);
            requires.push(className);
            if ((requireClasses = config.requireClasses)) {
                requires = requires.concat(requireClasses.split(','));
            }
        });
        Ext.require(requires, adder);
        Ext.defer(hider, 5000);
    },
    showView: function(className) {
        var me = this;
        var view = me.mdiTab.down(Ext.String.format('>[classpath={0}]', className));
        if (view) {
            me.mdiTab.setActiveTab(view);
        }
        me.hideSpMain();
    },
    hasView: function(className) {
        var me = this;
        return !!me.mdiTab.down(Ext.String.format('>[classpath={0}]', className));
    },
    closeView: function(className) {
        var me = this,
            mdiTab = me.mdiTab,
            item = me.mdiTab.down(Ext.String.format('>[classpath={0}]', className));
        Ext.suspendLayouts();
        mdiTab.remove(item, false);
        Ext.defer(Ext.resumeLayouts, 10, null, [
            true
        ]);
        Ext.defer(function() {
            item.destroy();
        }, 100);
    },
    closeAll: function() {
        var me = this,
            mdiTab = me.mdiTab,
            closableItems = mdiTab.query('>[closable]');
        Ext.suspendLayouts();
        Ext.Array.each(closableItems, function(item) {
            mdiTab.remove(item, false);
        });
        Ext.defer(Ext.resumeLayouts, 10, null, [
            true
        ]);
        var clearIntervalId = Ext.interval(function() {
                var item = closableItems.shift();
                if (item) {
                    item.destroy();
                } else {
                    clearInterval(clearIntervalId);
                }
            }, 100);
    },
    replaceView: function(source, target) {
        var me = this,
            mdiTab = me.mdiTab;
        var sourceIndex = mdiTab.items.indexOf(source);
        if (sourceIndex > -1) {
            mdiTab.remove(source);
            target = mdiTab.insert(sourceIndex - 1, target);
            mdiTab.setActiveTab(target);
        } else {
            Ext.log({
                level: 'error'
            }, 'source view 를 찾을 수 없습니다.');
        }
    },
    init: function(mdiTab) {
        var me = this;
        me.mdiTab = mdiTab;
        me.mdiDisabled = !!Ext.isIE7;
        if (me.mdiDisabled) {
            var tabbar = mdiTab.getTabBar();
            tabbar.setHidden(true);
            me.mdiIFrame = mdiTab.add({
                xtype: 'mdiiframe'
            });
            mdiTab.setActiveTab(me.mdiIFrame);
        }
        //mdi iframe 
    }
   ,
    buildIFrameUrl: function(className, config, requireClasses) {
        return Ext.String.format('app.do?classpath={0}&requires={1}&header=false', className, requireClasses);
    },
    getCurrentLoale: function() {
        return new Promise(function(resolve, reject) {
            Ext.Ajax.request({
                url: 'api/mdi/currentLocale',
                method: 'GET',
                success: function(response) {
                    resolve(Ext.JSON.decode(response.responseText));
                },
                failure: function() {
                    reject();
                }
            });
        });
    },
    setCurrentLocale: function(locale) {
        Etna.i18n.Manager.clear();
        return new Promise(function(resolve, reject) {
            Ext.Ajax.request({
                url: 'api/mdi/currentLocale?' + Ext.Object.toQueryString({
                    locale: locale
                }),
                method: 'PUT',
                success: function() {
                    resolve();
                },
                failure: function() {
                    reject();
                }
            });
        });
    },
    getMessages: function(keys, locale) {
        return new Promise(function(resolve, reject) {
            Ext.Ajax.request({
                url: 'api/mdi/messages?' + Ext.Object.toQueryString({
                    locale: locale,
                    keys: keys.join(',')
                }),
                method: 'GET',
                success: function(response) {
                    resolve(Ext.JSON.decode(response.responseText));
                },
                failure: function() {
                    reject();
                }
            });
        });
    },
    setMessages: function(messages, locale) {
        return new Promise(function(resolve, reject) {
            Ext.Ajax.request({
                url: 'api/mdi/messages?' + Ext.Object.toQueryString({
                    locale: locale
                }),
                method: 'PUT',
                jsonData: messages,
                success: function(response) {
                    resolve();
                },
                failure: function() {
                    reject();
                }
            });
        });
    },
    getDisplayText: function() {
        return new Promise(function(resolve, reject) {
            Ext.Ajax.request({
                url: 'api/mdi/displayText',
                method: 'GET',
                success: function(response) {
                    resolve(response.responseText);
                },
                failure: function() {
                    reject();
                }
            });
        });
    },
    logout: function() {},
    refreshView: function(className) {
        var me = this,
            mdiTab = me.mdiTab;
        var view = mdiTab.down(Ext.String.format('>[classpath={0}]', className));
        if (view) {
            Ext.suspendLayouts();
            var next = view.nextSibling();
            var className = Ext.ClassManager.getName(view);
            var mdiConfig = view.mdiConfig;
            mdiTab.remove(view, true);
            me.addView(className, mdiConfig, null, function() {
                view = mdiTab.down(Ext.String.format('>[classpath={0}]', className));
                mdiTab.moveBefore(view, next);
                mdiTab.setActiveTab(view);
                Ext.resumeLayouts(true);
            });
        } else {
            Ext.log({
                level: 'error'
            }, 'view 를 찾을 수 없습니다.');
        }
    },
    constructor: function(config) {
        var me = this;
        if (!window.Promise) {
            window.Promise = ES6Promise.Promise;
        }
        if (me.mdiTabOverflow) {
            if (Ext.isFunction(me.mdiTabOverflow)) {
                me.mdiTabOverflow = me.mdiTabOverflow();
            } else if (Ext.isObject(me.mdiTabOverflow)) {
                Ext.iterate(me.mdiTabOverflow, function(key, value) {
                    if (Ext[key]) {
                        me.mdiTabOverflow = value;
                        return;
                    }
                });
            }
        }
        me.callParent(arguments);
    },
    isAuthenticated: function() {
        var me = this;
        if (Ext.isDefined(me.authenticated)) {
            return new Promise(function(resolve, reject) {
                resolve(me.authenticated);
            });
        } else {
            return new Promise(function(resolve, reject) {
                Ext.Ajax.request({
                    url: 'api/mdi/isAuthenticated',
                    method: 'GET',
                    success: function(response) {
                        me.authenticated = response.responseText == "true";
                        resolve(me.authenticated);
                    },
                    failure: function() {
                        reject();
                    }
                });
            });
        }
    },
    isMdiTabOverflow: function(addCount) {
        var me = this,
            mdiTab = me.mdiTab,
            overflow = MdiManager.mdiTabOverflow,
            count = mdiTab.items.filterBy(function(view) {
                return !view.tab.hidden;
            }).getCount() + (addCount || 1);
        if (overflow && count >= overflow) {
            return count - overflow;
        }
        return false;
    },
    processMdiTabViewConfig: function(className, config) {
        var me = this;
        return Ext.apply(config, {
            xclass: className,
            tabConfig: {
                listeners: {
                    beforeclose: function(tab) {
                        Ext.suspendLayouts();
                        var nextActiveTab = tab.tabBar.findNextActivatable(tab);
                        tab.hide();
                        tab.card.hide();
                        if (nextActiveTab && nextActiveTab.card) {
                            me.mdiTab.setActiveTab(nextActiveTab.card);
                        }
                        Ext.resumeLayouts(true);
                        Ext.defer(function() {
                            me.mdiTab.tabBar.closeTab(tab);
                        }, 500);
                        return false;
                    },
                    single: true,
                    scope: me
                }
            }
        });
    },
    mdiTabOverflowHandler: function(className, config, requireClasses, callback) {
        var me = this;
		var popup = Ext.create('Mdi.view.mdi.popup.MdiTabOverflowPopup', {
			mdiTabOverflow : me.mdiTabOverflow,
			listeners : {
				addview : function() {
					MdiManager.addView(className, config, requireClasses, callback);
				}
			}
		});
		popup.loadTabs(me.mdiTab);
    },
    resizeHandler : function() {
    	var me = this;
    	if(me.spmain) {
    		if(isForeign){
    			me.spmain.setHeight(Ext.getBody().getHeight());
    		}else{
    			me.spmain.setHeight(Ext.getBody().getHeight() - 100);
    		}
    		
    	} 
    },
    
    showSpMain : function(){
    	
    	var loadUrl = 'main/splogin.jsp';
    	var topSize = 75;
    	var heightSize = 'calc(100% - 75px)';
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
    
    hideSpMain : function (){
    	var me = this;
    	Ext.getWin().un('resize', me.resizeHandler, me);
    	if(me.spmain) {
    		if(me.mdiTab){
    			me.mdiTab.show();
    		}
    		me.spmain.destroy();
    		delete me.spmain;
    	}
    	
    	var viewPort = me.mdiTab.up();
    	viewPort.lookupReference('mdiTabPanel').show();
    	viewPort.lookupReference('tools').setHeight('100%')
    	viewPort.down('mdileft').show();
    	viewPort.down('mditop').items.items[2].show();
    },

    toggleSpMain : function(param){
    	
    	var me = this;
    	if(me.spmain){
    		me.hideSpMain();
    	}
    	else{
    		isForeign = param;
    		me.showSpMain();
    	}
    }
});

/*
 * File: app/model/App.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.model.App', {
    extend: Ext.data.Model,
    fields: [
        {
            type: 'string',
            name: 'superId'
        },
        {
            type: 'string',
            name: 'appId'
        },
        {
            type: 'string',
            name: 'name'
        },
        {
            type: 'string',
            name: 'code'
        },
        {
            type: 'string',
            name: 'classpath'
        },
        {
            type: 'int',
            name: 'orderNo'
        },
        {
            type: 'string',
            name: 'appStyle'
        },
        {
            type: 'string',
            name: 'appIconStyle'
        },
        {
            type: 'boolean',
            name: 'leaf'
        },
        {
            type: 'string',
            name: 'requireClass'
        },
        {
            type: 'boolean',
            convert: function(v, rec) {
                if (rec.get('code')) {
                    return rec.get('children') ? rec.get('children').length > 0 : false;
                }
                return true;
            },
            name: 'folder'
        },
        {
            type: 'boolean',
            defaultValue: false,
            name: 'installed'
        },
        {
            type: 'boolean',
            defaultValue: false,
            name: 'role'
        }
    ],
    isFolder: function() {
        return this.get('folder');
    },
    hasRole: function() {
        return this.get('role');
    }
});

/*
 * File: app/model/I18n.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.model.I18n', {
    extend: Ext.data.Model,
    fields: [
        {
            type: 'string',
            name: 'key'
        },
        {
            type: 'string',
            name: 'value'
        }
    ]
});

/*
 * File: app/model/Menu.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.model.Menu', {
    extend: Ext.data.Model,
    fields: [
        {
            type: 'string',
            name: 'classpath'
        },
        {
            type: 'string',
            name: 'id'
        },
        {
            type: 'string',
            name: 'text'
        },
        {
            type: 'boolean',
            name: 'isLeaf'
        },
        {
            type: 'boolean',
            name: 'isUse'
        },
        {
            type: 'int',
            name: 'order'
        },
        {
            type: 'string',
            name: 'iconCls'
        },
        {
            type: 'string',
            name: 'code'
        },
        {
            type: 'string',
            name: 'requireClass'
        }
    ]
});

/*
 * File: app/model/Setting.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.model.Setting', {
    extend: Ext.data.Model,
    singleton: true,
    fields: [
        {
            type: 'boolean',
            defaultValue: false,
            name: 'authenticatable'
        },
        {
            type: 'string',
            defaultValue: 'Disclosed',
            name: 'kind'
        },
        {
            type: 'string',
            defaultValue: 'Mdi.view.mdi.authenticator.Standard',
            name: 'authenticatorClass'
        },
        {
            type: 'string',
            defaultValue: 'default',
            name: 'topMenuMode'
        }
    ]
});

/*
 * File: app/store/Locale.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.store.Locale', {
    extend: Ext.data.Store,
    singleton: true,
    constructor: function(cfg) {
        var me = this;
        cfg = cfg || {};
        me.callParent([
            Ext.apply({
                storeId: 'mdiLocale',
                autoLoad: true,
                fields: [
                    {
                        type: 'string',
                        mapping: 'locale',
                        name: 'key'
                    },
                    {
                        type: 'string',
                        mapping: 'name',
                        name: 'value'
                    }
                ],
                proxy: {
                    type: 'rest',
                    url: 'api/mdi/supportedLocales'
                }
            }, cfg)
        ]);
    }
});

/*
 * File: app/store/Menu.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.store.Menu', {
    extend: Ext.data.TreeStore,
    singleton: true,
    config: {
        i18nKeys: []
    },
    constructor: function(cfg) {
        var me = this;
        cfg = cfg || {};
        me.callParent([
            Ext.apply({
                storeId: 'mdiMenu',
                model: 'Mdi.model.Menu',
                root: {
                    text: '',
                    loaded: true
                },
                proxy: {
                    type: 'rest',
                    url: 'api/mdi/menus',
                    appendId: false,
                    reader: {
                        type: 'json',
                        transform: {
                            type: 'hierarchy',
                            idProperty: 'id',
                            parentProperty: 'superId',
                            rootId: null,
                            includeRoot: false,
                            interceptor: function(record, level, leaf) {
                                record.leaf = leaf;
                                if (Etna.i18n.Manager.isI18nValue(record.text)) {
                                    Mdi.store.Menu.getI18nKeys().push(Etna.i18n.Manager.getI18nKey(record.text));
                                }
                            }
                        }
                    }
                },
                sorters: {
                    property: 'order'
                }
            }, cfg)
        ]);
    },
    applyProxy: function(proxy) {
        proxy = Ext.data.TreeStore.prototype.applyProxy.call(this, proxy);
        Ext.apply(proxy.getReader(), {
            getData: function(o) {
                var i18nKeys = Mdi.store.Menu.getI18nKeys();
                if (i18nKeys.length > 0) {
                    var provider = Etna.i18n.Manager.getProvider(),
                        storage = Etna.i18n.Manager.getStorage();
                    storage.get(i18nKeys, Etna.i18n.Manager.getLocale());
                    i18nKeys.length = 0;
                }
                return Ext.identityFn.call(this, o);
            }
        });
        return proxy;
    }
});

/*
 * File: app/store/UnauthorizedMenu.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.store.UnauthorizedMenu', {
    extend: Ext.data.Store,
    singleton: true,
    config: {
        i18nKeys: []
    },
    constructor: function(cfg) {
        var me = this;
        cfg = cfg || {};
        me.callParent([
            Ext.apply({
                storeId: 'UnauthorizedMenu',
                model: 'Mdi.model.Menu',
                proxy: {
                    type: 'rest',
                    url: 'api/mdi/unauthorizedMenus',
                    reader: {
                        type: 'json',
                        transform: {
                            fn: function(datas) {
                                Ext.Array.each(datas, function(data) {
                                    if (Etna.i18n.Manager.isI18nValue(data.text)) {
                                        Mdi.store.UnauthorizedMenu.getI18nKeys().push(Etna.i18n.Manager.getI18nKey(data.text));
                                    }
                                });
                                return datas;
                            }
                        }
                    }
                }
            }, cfg)
        ]);
    },
    applyProxy: function(proxy) {
        proxy = Ext.data.Store.prototype.applyProxy.call(this, proxy);
        Ext.apply(proxy.getReader(), {
            getData: function(o) {
                var i18nKeys = Mdi.store.UnauthorizedMenu.getI18nKeys();
                if (i18nKeys.length > 0) {
                    var provider = Etna.i18n.Manager.getProvider(),
                        storage = Etna.i18n.Manager.getStorage();
                    storage.get(i18nKeys, Etna.i18n.Manager.getLocale());
                    i18nKeys.length = 0;
                }
                return Ext.identityFn.call(this, o);
            }
        });
        return proxy;
    }
});

/**
 * Base class from Ext.ux.TabReorderer.
 */
Ext.define('Mdi.ux.BoxReorderer', {
    mixins: {
        observable: Ext.util.Observable
    },
    /**
     * @cfg {String} itemSelector
     * A {@link Ext.DomQuery DomQuery} selector which identifies the encapsulating elements of child
     * Components which participate in reordering.
     */
    itemSelector: '.x-box-item',
    /**
     * @cfg {Mixed} animate
     * If truthy, child reordering is animated so that moved boxes slide smoothly into position.
     * If this option is numeric, it is used as the animation duration in milliseconds.
     */
    animate: 100,
    /**
     * @event StartDrag
     * Fires when dragging of a child Component begins.
     * @param {Ext.ux.BoxReorderer} this
     * @param {Ext.container.Container} container The owning Container
     * @param {Ext.Component} dragCmp The Component being dragged
     * @param {Number} idx The start index of the Component being dragged.
     */
    /**
     * @event Drag
     * Fires during dragging of a child Component.
     * @param {Ext.ux.BoxReorderer} this
     * @param {Ext.container.Container} container The owning Container
     * @param {Ext.Component} dragCmp The Component being dragged
     * @param {Number} startIdx The index position from which the Component was initially dragged.
     * @param {Number} idx The current closest index to which the Component would drop.
     */
    /**
     * @event ChangeIndex
     * Fires when dragging of a child Component causes its drop index to change.
     * @param {Ext.ux.BoxReorderer} this
     * @param {Ext.container.Container} container The owning Container
     * @param {Ext.Component} dragCmp The Component being dragged
     * @param {Number} startIdx The index position from which the Component was initially dragged.
     * @param {Number} idx The current closest index to which the Component would drop.
     */
    /**
     * @event Drop
     * Fires when a child Component is dropped at a new index position.
     * @param {Ext.ux.BoxReorderer} this
     * @param {Ext.container.Container} container The owning Container
     * @param {Ext.Component} dragCmp The Component being dropped
     * @param {Number} startIdx The index position from which the Component was initially dragged.
     * @param {Number} idx The index at which the Component is being dropped.
     */
    constructor: function() {
        this.mixins.observable.constructor.apply(this, arguments);
    },
    init: function(container) {
        var me = this;
        me.container = container;
        // Set our animatePolicy to animate the start position (ie x for HBox, y for VBox)
        me.animatePolicy = {};
        me.animatePolicy[container.getLayout().names.x] = true;
        // Initialize the DD on first layout, when the innerCt has been created.
        me.container.on({
            scope: me,
            boxready: me.onBoxReady,
            beforedestroy: me.onContainerDestroy
        });
    },
    /**
     * @private Clear up on Container destroy
     */
    onContainerDestroy: function() {
        var dd = this.dd;
        if (dd) {
            dd.unreg();
            this.dd = null;
        }
    },
    onBoxReady: function() {
        var me = this,
            layout = me.container.getLayout(),
            names = layout.names,
            dd;
        // Create a DD instance. Poke the handlers in.
        // TODO: Ext5's DD classes should apply config to themselves.
        // TODO: Ext5's DD classes should not use init internally because it collides with use as a plugin
        // TODO: Ext5's DD classes should be Observable.
        // TODO: When all the above are trus, this plugin should extend the DD class.
        dd = me.dd = new Ext.dd.DD(layout.innerCt, me.container.id + '-reorderer');
        Ext.apply(dd, {
            animate: me.animate,
            reorderer: me,
            container: me.container,
            getDragCmp: me.getDragCmp,
            clickValidator: Ext.Function.createInterceptor(dd.clickValidator, me.clickValidator, me, false),
            onMouseDown: me.onMouseDown,
            startDrag: me.startDrag,
            onDrag: me.onDrag,
            endDrag: me.endDrag,
            getNewIndex: me.getNewIndex,
            doSwap: me.doSwap,
            findReorderable: me.findReorderable
        });
        // Decide which dimension we are measuring, and which measurement metric defines
        // the *start* of the box depending upon orientation.
        dd.dim = names.width;
        dd.startAttr = names.beforeX;
        dd.endAttr = names.afterX;
    },
    getDragCmp: function(e) {
        return this.container.getChildByElement(e.getTarget(this.itemSelector, 10));
    },
    // check if the clicked component is reorderable
    clickValidator: function(e) {
        var cmp = this.getDragCmp(e);
        // If cmp is null, this expression MUST be coerced to boolean so that createInterceptor is able to test it against false
        return !!(cmp && cmp.reorderable !== false);
    },
    onMouseDown: function(e) {
        var me = this,
            container = me.container,
            containerBox, cmpEl, cmpBox;
        // Ascertain which child Component is being mousedowned
        me.dragCmp = me.getDragCmp(e);
        if (me.dragCmp) {
            cmpEl = me.dragCmp.getEl();
            me.startIndex = me.curIndex = container.items.indexOf(me.dragCmp);
            // Start position of dragged Component
            cmpBox = cmpEl.getBox();
            // Last tracked start position
            me.lastPos = cmpBox[me.startAttr];
            // Calculate constraints depending upon orientation
            // Calculate offset from mouse to dragEl position
            containerBox = container.el.getBox();
            if (me.dim === 'width') {
                me.minX = containerBox.left;
                me.maxX = containerBox.right - cmpBox.width;
                me.minY = me.maxY = cmpBox.top;
                me.deltaX = e.getX() - cmpBox.left;
            } else {
                me.minY = containerBox.top;
                me.maxY = containerBox.bottom - cmpBox.height;
                me.minX = me.maxX = cmpBox.left;
                me.deltaY = e.getY() - cmpBox.top;
            }
            me.constrainY = me.constrainX = true;
        }
    },
    startDrag: function() {
        var me = this,
            dragCmp = me.dragCmp;
        if (dragCmp) {
            // For the entire duration of dragging the *Element*, defeat any positioning and animation of the dragged *Component*
            dragCmp.setPosition = Ext.emptyFn;
            dragCmp.animate = false;
            // Animate the BoxLayout just for the duration of the drag operation.
            if (me.animate) {
                me.container.getLayout().animatePolicy = me.reorderer.animatePolicy;
            }
            // We drag the Component element
            me.dragElId = dragCmp.getEl().id;
            me.reorderer.fireEvent('StartDrag', me, me.container, dragCmp, me.curIndex);
            // Suspend events, and set the disabled flag so that the mousedown and mouseup events
            // that are going to take place do not cause any other UI interaction.
            dragCmp.suspendEvents();
            dragCmp.disabled = true;
            dragCmp.el.setStyle('zIndex', 100);
        } else {
            me.dragElId = null;
        }
    },
    /**
     * @private
     * Find next or previous reorderable component index.
     * @param {Number} newIndex The initial drop index.
     * @return {Number} The index of the reorderable component.
     */
    findReorderable: function(newIndex) {
        var me = this,
            items = me.container.items,
            newItem;
        if (items.getAt(newIndex).reorderable === false) {
            newItem = items.getAt(newIndex);
            if (newIndex > me.startIndex) {
                while (newItem && newItem.reorderable === false) {
                    newIndex++;
                    newItem = items.getAt(newIndex);
                }
            } else {
                while (newItem && newItem.reorderable === false) {
                    newIndex--;
                    newItem = items.getAt(newIndex);
                }
            }
        }
        newIndex = Math.min(Math.max(newIndex, 0), items.getCount() - 1);
        if (items.getAt(newIndex).reorderable === false) {
            return -1;
        }
        return newIndex;
    },
    /**
     * @private
     * Swap 2 components.
     * @param {Number} newIndex The initial drop index.
     */
    doSwap: function(newIndex) {
        var me = this,
            items = me.container.items,
            container = me.container,
            wasRoot = me.container._isLayoutRoot,
            orig, dest, tmpIndex;
        newIndex = me.findReorderable(newIndex);
        if (newIndex === -1) {
            return;
        }
        me.reorderer.fireEvent('ChangeIndex', me, container, me.dragCmp, me.startIndex, newIndex);
        orig = items.getAt(me.curIndex);
        dest = items.getAt(newIndex);
        items.remove(orig);
        tmpIndex = Math.min(Math.max(newIndex, 0), items.getCount() - 1);
        items.insert(tmpIndex, orig);
        items.remove(dest);
        items.insert(me.curIndex, dest);
        // Make the Box Container the topmost layout participant during the layout.
        container._isLayoutRoot = true;
        container.updateLayout();
        container._isLayoutRoot = wasRoot;
        me.curIndex = newIndex;
    },
    onDrag: function(e) {
        var me = this,
            newIndex;
        newIndex = me.getNewIndex(e.getPoint());
        if ((newIndex !== undefined)) {
            me.reorderer.fireEvent('Drag', me, me.container, me.dragCmp, me.startIndex, me.curIndex);
            me.doSwap(newIndex);
        }
    },
    endDrag: function(e) {
        if (e) {
            e.stopEvent();
        }
        var me = this,
            layout = me.container.getLayout(),
            temp;
        if (me.dragCmp) {
            delete me.dragElId;
            // Reinstate the Component's positioning method after mouseup, and allow the layout system to animate it.
            delete me.dragCmp.setPosition;
            me.dragCmp.animate = true;
            // Ensure the lastBox is correct for the animation system to restore to when it creates the "from" animation frame
            me.dragCmp.lastBox[layout.names.x] = me.dragCmp.getPosition(true)[layout.names.widthIndex];
            // Make the Box Container the topmost layout participant during the layout.
            me.container._isLayoutRoot = true;
            me.container.updateLayout();
            me.container._isLayoutRoot = undefined;
            // Attempt to hook into the afteranimate event of the drag Component to call the cleanup
            temp = Ext.fx.Manager.getFxQueue(me.dragCmp.el.id)[0];
            if (temp) {
                temp.on({
                    afteranimate: me.reorderer.afterBoxReflow,
                    scope: me
                });
            } else // If not animated, clean up after the mouseup has happened so that we don't click the thing being dragged
            {
                Ext.Function.defer(me.reorderer.afterBoxReflow, 1, me);
            }
            if (me.animate) {
                delete layout.animatePolicy;
            }
            me.reorderer.fireEvent('drop', me, me.container, me.dragCmp, me.startIndex, me.curIndex);
        }
    },
    /**
     * @private
     * Called after the boxes have been reflowed after the drop.
     * Re-enabled the dragged Component.
     */
    afterBoxReflow: function() {
        var me = this;
        me.dragCmp.el.setStyle('zIndex', '');
        me.dragCmp.disabled = false;
        me.dragCmp.resumeEvents();
    },
    /**
     * @private
     * Calculate drop index based upon the dragEl's position.
     */
    getNewIndex: function(pointerPos) {
        var me = this,
            dragEl = me.getDragEl(),
            dragBox = Ext.fly(dragEl).getBox(),
            targetEl, targetBox, targetMidpoint,
            i = 0,
            it = me.container.items.items,
            ln = it.length,
            lastPos = me.lastPos;
        me.lastPos = dragBox[me.startAttr];
        for (; i < ln; i++) {
            targetEl = it[i].getEl();
            // Only look for a drop point if this found item is an item according to our selector
            if (targetEl.is(me.reorderer.itemSelector)) {
                targetBox = targetEl.getBox();
                targetMidpoint = targetBox[me.startAttr] + (targetBox[me.dim] >> 1);
                if (i < me.curIndex) {
                    if ((dragBox[me.startAttr] < lastPos) && (dragBox[me.startAttr] < (targetMidpoint - 5))) {
                        return i;
                    }
                } else if (i > me.curIndex) {
                    if ((dragBox[me.startAttr] > lastPos) && (dragBox[me.endAttr] > (targetMidpoint + 5))) {
                        return i;
                    }
                }
            }
        }
    }
});

/**
 * Plugin for adding a close context menu to tabs. Note that the menu respects
 * the closable configuration on the tab. As such, commands like remove others
 * and remove all will not remove items that are not closable.
 */
Ext.define('Mdi.ux.TabCloseMenu', {
    alias: 'plugin.mditabclosemenu',
    mixins: {
        observable: Ext.util.Observable
    },
    /**
     * @cfg {String} closeTabText
     * The text for closing the current tab.
     */
    closeTabText: 'Close Tab',
    /**
     * @cfg {Boolean} showCloseOthers
     * Indicates whether to show the 'Close Others' option.
     */
    showCloseOthers: true,
    /**
     * @cfg {String} closeOthersTabsText
     * The text for closing all tabs except the current one.
     */
    closeOthersTabsText: 'Close Other Tabs',
    /**
     * @cfg {Boolean} showCloseAll
     * Indicates whether to show the 'Close All' option.
     */
    showCloseAll: true,
    /**
     * @cfg {String} closeAllTabsText
     * The text for closing all tabs.
     */
    closeAllTabsText: 'Close All Tabs',
    /**
     * @cfg {Array} extraItemsHead
     * An array of additional context menu items to add to the front of the context menu.
     */
    extraItemsHead: null,
    /**
     * @cfg {Array} extraItemsTail
     * An array of additional context menu items to add to the end of the context menu.
     */
    extraItemsTail: null,
    // TODO - doc this.addEvents('aftermenu','beforemenu');
    //public
    constructor: function(config) {
        this.mixins.observable.constructor.call(this, config);
    },
    init: function(tabpanel) {
        this.tabPanel = tabpanel;
        this.tabBar = tabpanel.down("tabbar");
        this.mon(this.tabPanel, {
            scope: this,
            afterlayout: this.onAfterLayout,
            single: true
        });
    },
    onAfterLayout: function() {
        this.mon(this.tabBar.el, {
            scope: this,
            contextmenu: this.onContextMenu,
            delegate: '.x-tab'
        });
    },
    onBeforeDestroy: function() {
        Ext.destroy(this.menu);
        this.callParent(arguments);
    },
    // private
    onContextMenu: function(event, target) {
        var me = this,
            menu = me.createMenu(),
            disableAll = true,
            disableOthers = true,
            tab = me.tabBar.getChildByElement(target),
            index = me.tabBar.items.indexOf(tab);
        me.item = me.tabPanel.getComponent(index);
        menu.child('#close').setDisabled(!me.item.closable);
        if (me.showCloseAll || me.showCloseOthers) {
            me.tabPanel.items.each(function(item) {
                if (item.closable) {
                    disableAll = false;
                    if (item != me.item) {
                        disableOthers = false;
                        return false;
                    }
                }
                return true;
            });
            if (me.showCloseAll) {
                menu.child('#closeAll').setDisabled(disableAll);
            }
            if (me.showCloseOthers) {
                menu.child('#closeOthers').setDisabled(disableOthers);
            }
        }
        event.preventDefault();
        me.fireEvent('beforemenu', menu, me.item, me);
        menu.showAt(event.getXY());
    },
    createMenu: function() {
        var me = this;
        if (!me.menu) {
            var items = [
                    {
                        itemId: 'close',
                        text: me.closeTabText,
                        scope: me,
                        handler: me.onClose
                    }
                ];
            if (me.showCloseAll || me.showCloseOthers) {
                items.push('-');
            }
            if (me.showCloseOthers) {
                items.push({
                    itemId: 'closeOthers',
                    text: me.closeOthersTabsText,
                    scope: me,
                    handler: me.onCloseOthers
                });
            }
            if (me.showCloseAll) {
                items.push({
                    itemId: 'closeAll',
                    text: me.closeAllTabsText,
                    scope: me,
                    handler: me.onCloseAll
                });
            }
            if (me.extraItemsHead) {
                items = me.extraItemsHead.concat(items);
            }
            if (me.extraItemsTail) {
                items = items.concat(me.extraItemsTail);
            }
            me.menu = Ext.create('Ext.menu.Menu', {
                items: items,
                listeners: {
                    hide: me.onHideMenu,
                    scope: me
                }
            });
        }
        return me.menu;
    },
    onHideMenu: function() {
        var me = this;
        me.fireEvent('aftermenu', me.menu, me);
    },
    onClose: function() {
        this.tabPanel.remove(this.item);
    },
    onCloseOthers: function() {
        this.doClose(true);
    },
    onCloseAll: function() {
        this.doClose(false);
    },
    doClose: function(excludeActive) {
        var items = [];
        this.tabPanel.items.each(function(item) {
            if (item.closable) {
                if (!excludeActive || item != this.item) {
                    items.push(item);
                }
            }
        }, this);
        Ext.suspendLayouts();
        Ext.Array.forEach(items, function(item) {
            this.tabPanel.remove(item);
        }, this);
        Ext.resumeLayouts(true);
    }
});

/**
 * This plugin allow you to reorder tabs of a TabPanel.
 */
Ext.define('Mdi.ux.TabReorderer', {
    extend: Mdi.ux.BoxReorderer,
    alias: 'plugin.mditabreorderer',
    itemSelector: '.' + Ext.baseCSSPrefix + 'tab',
    init: function(tabPanel) {
        var me = this;
        me.callParent([
            tabPanel.getTabBar()
        ]);
        // Ensure reorderable property is copied into dynamically added tabs
        tabPanel.onAdd = Ext.Function.createSequence(tabPanel.onAdd, me.onAdd);
    },
    onBoxReady: function() {
        var tabs, len,
            i = 0,
            tab;
        this.callParent(arguments);
        // Copy reorderable property from card into tab
        for (tabs = this.container.items.items , len = tabs.length; i < len; i++) {
            tab = tabs[i];
            if (tab.card) {
                tab.reorderable = tab.card.reorderable;
            }
        }
    },
    onAdd: function(card, index) {
        card.tab.reorderable = card.reorderable;
    },
    afterBoxReflow: function() {
        var me = this;
        // Cannot use callParent, this is not called in the scope of this plugin, but that of its Ext.dd.DD object
        Mdi.ux.BoxReorderer.prototype.afterBoxReflow.apply(me, arguments);
        // Move the associated card to match the tab order
        if (me.dragCmp) {
            me.container.tabPanel.setActiveTab(me.dragCmp.card);
            me.container.tabPanel.move(me.startIndex, me.curIndex);
        }
    }
});

/**
 * Plugin for adding a tab menu to a TabBar is the Tabs overflow.
 */
Ext.define('Mdi.ux.TabScrollerMenu', {
    alias: 'plugin.mditabscrollermenu',
    /**
     * @cfg {Number} pageSize How many items to allow per submenu.
     */
    pageSize: 10,
    /**
     * @cfg {Number} maxText How long should the title of each {@link Ext.menu.Item} be.
     */
    maxText: 15,
    /**
     * @cfg {String} menuPrefixText Text to prefix the submenus.
     */
    menuPrefixText: 'Items',
    /**
     * Creates new TabScrollerMenu.
     * @param {Object} config Configuration options
     */
    constructor: function(config) {
        Ext.apply(this, config);
    },
    //private
    init: function(tabPanel) {
        var me = this;
        me.tabPanel = tabPanel;
        tabPanel.on({
            render: function() {
                me.tabBar = tabPanel.tabBar;
                me.layout = me.tabBar.layout;
                me.layout.overflowHandler.handleOverflow = Ext.Function.bind(me.showButton, me);
                me.layout.overflowHandler.clearOverflow = Ext.Function.createSequence(me.layout.overflowHandler.clearOverflow, me.hideButton, me);
            },
            destroy: me.destroy,
            scope: me,
            single: true
        });
    },
    showButton: function() {
        var me = this,
            result = Ext.getClass(me.layout.overflowHandler).prototype.handleOverflow.apply(me.layout.overflowHandler, arguments),
            button = me.menuButton;
        if (me.tabPanel.items.getCount() > 1) {
            if (!button) {
                button = me.menuButton = me.tabBar.body.createChild({
                    cls: Ext.baseCSSPrefix + 'tab-tabmenu-right'
                }, me.tabBar.body.child('.' + Ext.baseCSSPrefix + 'box-scroller-right'));
                button.addClsOnOver(Ext.baseCSSPrefix + 'tab-tabmenu-over');
                button.on('click', me.showTabsMenu, me);
            }
            button.setVisibilityMode(Ext.dom.Element.DISPLAY);
            button.show();
            result.reservedSpace += button.getWidth();
        } else {
            me.hideButton();
        }
        return result;
    },
    hideButton: function() {
        var me = this;
        if (me.menuButton) {
            me.menuButton.hide();
        }
    },
    /**
     * Returns an the current page size (this.pageSize);
     * @return {Number} this.pageSize The current page size.
     */
    getPageSize: function() {
        return this.pageSize;
    },
    /**
     * Sets the number of menu items per submenu "page size".
     * @param {Number} pageSize The page size
     */
    setPageSize: function(pageSize) {
        this.pageSize = pageSize;
    },
    /**
     * Returns the current maxText length;
     * @return {Number} this.maxText The current max text length.
     */
    getMaxText: function() {
        return this.maxText;
    },
    /**
     * Sets the maximum text size for each menu item.
     * @param {Number} t The max text per each menu item.
     */
    setMaxText: function(t) {
        this.maxText = t;
    },
    /**
     * Returns the current menu prefix text String.;
     * @return {String} this.menuPrefixText The current menu prefix text.
     */
    getMenuPrefixText: function() {
        return this.menuPrefixText;
    },
    /**
     * Sets the menu prefix text String.
     * @param {String} t The menu prefix text.
     */
    setMenuPrefixText: function(t) {
        this.menuPrefixText = t;
    },
    showTabsMenu: function(e) {
        var me = this;
        if (me.tabsMenu) {
            me.tabsMenu.removeAll();
        } else {
            me.tabsMenu = new Ext.menu.Menu();
        }
        me.generateTabMenuItems();
        var target = Ext.get(e.getTarget()),
            xy = target.getXY();
        //Y param + 24 pixels
        xy[1] += 24;
        me.tabsMenu.showAt(xy);
    },
    // private
    generateTabMenuItems: function() {
        var me = this,
            tabPanel = me.tabPanel,
            curActive = tabPanel.getActiveTab(),
            allItems = tabPanel.items.getRange(),
            pageSize = me.getPageSize(),
            tabsMenu = me.tabsMenu,
            totalItems, numSubMenus, remainder, i, curPage, menuItems, x, item, start, index;
        tabsMenu.suspendLayouts();
        allItems = Ext.Array.filter(allItems, function(item) {
            if (item.id == curActive.id) {
                return false;
            }
            return item.hidden ? !!item.hiddenByLayout : true;
        });
        totalItems = allItems.length;
        numSubMenus = Math.floor(totalItems / pageSize);
        remainder = totalItems % pageSize;
        if (totalItems > pageSize) {
            // Loop through all of the items and create submenus in chunks of 10
            for (i = 0; i < numSubMenus; i++) {
                curPage = (i + 1) * pageSize;
                menuItems = [];
                for (x = 0; x < pageSize; x++) {
                    index = x + curPage - pageSize;
                    item = allItems[index];
                    menuItems.push(me.autoGenMenuItem(item));
                }
                tabsMenu.add({
                    text: me.getMenuPrefixText() + ' ' + (curPage - pageSize + 1) + ' - ' + curPage,
                    menu: menuItems
                });
            }
            // remaining items
            if (remainder > 0) {
                start = numSubMenus * pageSize;
                menuItems = [];
                for (i = start; i < totalItems; i++) {
                    item = allItems[i];
                    menuItems.push(me.autoGenMenuItem(item));
                }
                me.tabsMenu.add({
                    text: me.menuPrefixText + ' ' + (start + 1) + ' - ' + (start + menuItems.length),
                    menu: menuItems
                });
            }
        } else {
            for (i = 0; i < totalItems; ++i) {
                tabsMenu.add(me.autoGenMenuItem(allItems[i]));
            }
        }
        tabsMenu.resumeLayouts(true);
    },
    // private
    autoGenMenuItem: function(item) {
        var maxText = this.getMaxText(),
            text = Ext.util.Format.ellipsis(item.title, maxText);
        return {
            text: text,
            handler: this.showTabFromMenu,
            scope: this,
            disabled: item.disabled,
            tabToShow: item,
            iconCls: item.iconCls
        };
    },
    // private
    showTabFromMenu: function(menuItem) {
        this.tabPanel.setActiveTab(menuItem.tabToShow);
    },
    destroy: function() {
        Ext.destroy(this.tabsMenu, this.menuButton);
    }
});

/*
 * File: app/view/mdi/I18nEditorViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.I18nEditorViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mdii18neditor',
    data: {
        locale: null
    },
    stores: {
        i18nStore: {
            model: 'Mdi.model.I18n',
            proxy: {
                type: 'rest',
                url: 'api/mdi/messages'
            }
        },
        localeStore: {
            source: 'mdiLocale'
        }
    }
});

/*
 * File: app/view/mdi/I18nEditorViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.I18nEditorViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mdii18neditor',
    load: function(className, locale) {
        var me = this,
            store = me.getViewModel().get('i18nStore'),
            locale = locale || me.getViewModel().get('locale'),
            i18nKeys = [];
         //className = 'Ext.panel.Panel'; //목록 테스트용
        //i18nKeys.push('a');//목록 테스트용
        if (!className) {
            store.removeAll();
            return;
        }
        me.className = className;
        var prototypes = [];
        var prototype = Ext.ClassManager.get(className).prototype;
        prototypes.push(prototype);
        var requirePrototypeCollector = function(p) {
                if (!p) {
                    return;
                }
                if (p.requires) {
                    var requirePrototypes = [];
                    Ext.each(p.requires, function(require) {
                        if (require) {
                            requirePrototypeCollector(require.prototype);
                            requirePrototypes.push(require.prototype);
                        }
                    });
                    prototypes = Ext.Array.merge(prototypes, requirePrototypes);
                }
            };
        requirePrototypeCollector(prototype);
        var handler = function(p) {
                if (!p) {
                    return;
                }
                if (p.i18n && p.i18n.length) {
                    i18nKeys = Ext.Array.merge(p.i18n, i18nKeys);
                }
                if (p.requires) {
                    Ext.each(p.requires, function(r) {
                        if (r && r.prototype) {
                            handler(r.prototype);
                        }
                    });
                }
            };
        Ext.each(prototypes, handler);
        MdiManager.getMessages(i18nKeys, locale).then(function(messages) {
            store.removeAll();
            var list = [];
            Ext.iterate(messages, function(key, value) {
                list.push({
                    key: key,
                    value: value
                });
            });
            store.loadData(list);
        }, function() {
            Ext.MessageBox.alert("#{오류}", "#{다국어 정보 조회시 오류가 발생하였습니다.}");
        });
    },
    init: function() {
        var me = this,
            view = me.getView();
        view.load = Ext.Function.bind(me.load, me);
    },
    save: function(locale) {
        var me = this,
            view = me.getView(),
            vm = me.getViewModel();
        var store = vm.get('i18nStore');
        var values = {};
        var records = store.getNewRecords().concat(store.getModifiedRecords());
        Ext.each(records, function(record) {
            values[record.get('key')] = record.get('value');
        });
        view.setLoading(true);
        MdiManager.setMessages(values, locale).then(function(messages) {
            store.commitChanges();
            Ext.MessageBox.alert("#{알림}", "#{다국어 정보 저장 되었습니다.}");
            view.setLoading(false);
        }, function() {
            Ext.MessageBox.alert("#{오류}", "#{다국어 정보 저장시 오류가 발생하였습니다.}");
            view.setLoading(false);
        });
    },
    validateGrid: function() {
        var me = this,
            grid = me.lookupReference('i18nGrid'),
            store = me.getStore('i18nStore'),
            datas = store.getRange(),
            result = true;
        for (var i = 0; i < datas.length; i++) {
            if (Ext.String.trim(datas[i].get('key')) === '') {
                result = false;
                Etna.Message.alert('#{key 값을 입력해주세요}');
                grid.getSelectionModel().select(store.getAt(i));
                break;
            }
        }
        return result;
    },
    onLocaleChange: function(field, newValue, oldValue, eOpts) {
        var me = this;
        me.load(me.className, newValue);
    },
    onAddButtonClick: function(button, e, eOpts) {
        var store = this.getViewModel().getStore('i18nStore');
        var records = store.add({});
    },
    onSaveButtonClick: function(button, e, eOpts) {
        var me = this;
        var view = me.getView();
        var vm = me.getViewModel();
        var locale = vm.get('locale');
        if (me.validateGrid()) {
            me.save(locale);
        }
    },
    onViewAfterRender: function(component, eOpts) {
        var me = this,
            view = me.getView(),
            vm = me.getViewModel();
        vm.set('locale', vm.getStore('localeStore').first().get('key'));
    }
});

/*
 * File: app/view/mdi/I18nEditor.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
/*
    작성자 : 고재훈
*/
Ext.define('Mdi.view.mdi.I18nEditor', {
    extend: Ext.panel.Panel,
    alias: 'widget.mdii18neditor',
    controller: 'mdii18neditor',
    viewModel: {
        type: 'mdii18neditor'
    },
    height: 400,
    width: 600,
    layout: 'fit',
    title: '#{internationalization}',
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
                }
            ]
        }
    ],
    listeners: {
        afterrender: 'onViewAfterRender'
    },
    initConfig: function(instanceConfig) {
        var me = this,
            config = {
                items: [
                    {
                        xtype: 'gridpanel',
                        itemId: 'grid',
                        columnLines: true,
                        bind: {
                            store: '{i18nStore}'
                        },
                        columns: [
                            {
                                xtype: 'etnastatuscolumn',
                                width: 50,
                                dataIndex: 'status',
                                text: '#{status}'
                            },
                            {
                                xtype: 'gridcolumn',
                                dataIndex: 'key',
                                text: '#{key}',
                                flex: 1,
                                editor: {
                                    xtype: 'textfield',
                                    allowBlank: false
                                }
                            },
                            {
                                xtype: 'gridcolumn',
                                dataIndex: 'value',
                                text: '#{value}',
                                flex: 1,
                                editor: {
                                    xtype: 'textfield',
                                    allowBlank: false
                                }
                            }
                        ],
                        plugins: [
                            Ext.create('Ext.grid.plugin.CellEditing', {})
                        ]
                    }
                ]
            };
        if (instanceConfig) {
            me.getConfigurator().merge(me, config, instanceConfig);
        }
        return me.callParent([
            config
        ]);
    }
});

/*
 * File: app/view/mdi/LeftViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.LeftViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mdileft',
    stores: {
        menuStore: {
            type: 'tree',
            model: 'Mdi.model.Menu',
            trackRemoved: false,
            clearRemovedOnLoad: false,
            data: [],
            proxy: {
                type: 'memory'
            }
        }
    }
});

/*
 * File: app/view/mdi/LeftViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.LeftViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mdileft',
    init: function() {
        var me = this,
            view = me.getView(),
            vm = me.getViewModel();
        Ext.apply(view, {
            setMenu: Ext.bind(me.setMenu, me),
            adjustWidth: Ext.bind(me.adjustWidth, me)
        });
        me.onCurrentMenuChange = Ext.Function.createBuffered(me.onCurrentMenuChange, 500, me);
        vm.bind('{currentMenu}', me.onCurrentMenuChange, me);
    },
    setMenu: function(menuData) {
        var me = this,
            store = me.getStore('menuStore'),
            pops = [
                'id',
                'text',
                'code',
                'classpath',
                'leaf',
                'order',
                'iconCls'
            ],
            rootNode = Ext.copyTo({
                children: [],
                expanded: true
            }, function(menu) {
                while (menu.parentNode && !menu.parentNode.isRoot()) {
                    menu = menu.parentNode;
                }
                return menu.getData();
            }(menuData), pops),
            map = {};
        if (store.getRoot().getId() == rootNode.id) {
            return;
        }
        map[menuData.getId()] = rootNode;
        menuData.cascadeBy(function(node) {
            if (menuData == node) {
                return;
            }
            var n = Ext.copyTo({
                    children: [],
                    expanded: false
                }, node.getData(), pops);
            map[node.getId()] = n;
            var r = map[node.parentNode.getId()];
            r.children.push(n);
        });
        store.setRoot(rootNode);
        me.getView().setTitle(menuData.get('text'));
        me.adjustWidth();
    },
    adjustWidth: function() {
        var me = this,
            view = me.getView();
        var showtip = function() {
                Ext.Array.each(view.el.query('table.x-grid-item'), function(item) {
                	Ext.Array.each(item.querySelectorAll('img'), function(img) {
                		img.setAttribute('alt', '');
                	});
                	
                    var node = Ext.fly(item);
                    var inner = node.down('div.x-grid-cell-inner');
                    var text = inner.down('span.x-tree-node-text');
                    var paddingLeft = inner.getStyle('padding-left').replace('px', '');
                    var paddingRight = inner.getStyle('padding-right').replace('px', '');
                    var maxWidth = node.getWidth() - text.getLeft() - paddingLeft - paddingRight;
                    if (maxWidth < text.getWidth()) {
                        node.dom.setAttribute('showtip', true);
                        var value = text.dom.innerHTML,
                            length = value.length;
                        while (maxWidth < text.getTextWidth()) {
                            text.dom.innerHTML = value.substring(0, length--) + '...';
                        }
                    } else {
                        node.dom.setAttribute('showtip', false);
                    }
                });
            };
        if (view.el) {
            showtip();
        }
    },
    onCurrentMenuChange: function(menu, oldMenu) {
        var me = this,
            view = me.getView(),
            store = me.getStore('menuStore'),
            root = store.getRoot();
        if (!menu || menu.isRoot()) {
            view.setSelection(null);
            return;
        }
        if (menu == oldMenu) {
            return;
        }
        if (view.collapsed) {
            return;
        }
        var node = root.findChild("id", menu.getId(), true);
        var n = node.parentNode;
        while (n) {
            if (!n.isExpanded()) {
                n.expand(false);
            }
            n = n.parentNode;
        }
        view.setSelection(node);
    },
    onLeftMenuCellClick: function(tableview, td, cellIndex, record, tr, rowIndex, e, eOpts) {
        var me = this,
            view = me.getView(),
            mdiViewPortViewModel = this.getView().up('mdiviewport').viewModel;
        
        if(e.target.tagName === 'IMG') {
        	e.target = e.target.parentElement.querySelector('span');
        }
        
        if (!record.isLeaf()) {
            if (record.isExpanded()) {
                record.collapse();
            } else {
                record.expand();
            }
            me.adjustWidth();
        } else {
        	if(record.get('code') === 'MEM10420'){
        		//입찰보증금 미지급 업체관리 메뉴
              var w = 780,
              h = 768,
              leftPosition = (screen.width-w)/2,
              topPosition = (screen.height-h)/2;
             // 문서번호 안전(정보)-2363('20.11.6)관련 테스트 ip 주소 대외 노출건 삭제 및 주석처리('20.11.12 신상훈)
             // 확인결과 해당메뉴 미개발됨(관련문서 자재(구매)-4783('16.9.29)) 
             // window.open('http://주소삭제/choi/default_list.jsp?p1='+ Cmmn.User.get('username'), 'print', 'location=no, width='+w+',height='+h+',top='+topPosition+',left='+leftPosition+',scrollbars=yes');
             // window.open('/?p1='+ Cmmn.User.get('username'), 'print', 'location=no, width='+w+',height='+h+',top='+topPosition+',left='+leftPosition+',scrollbars=yes');
        	}else{
        		/*
        		 * 20.01.22 임상근 통합검색 Left Menu 클릭시 breadCrumb에 해당 메뉴 표시되도록 수정,
        		 * 2 티어 메뉴에서 탭 변경 후 복귀하여 다른 메뉴 클릭하면 기존 메뉴 select가 풀리지 않던 현상 수정
        		 */
        		if(record.get('code').indexOf('SEARCH') != -1) {
                    var nodes = tableview.getNodes();
                    for(var i=0; i < nodes.length; i++) {
                        var node = nodes[i];
                        if(node.classList.contains(tableview.selectedItemCls)){
                            node.classList.remove(tableview.selectedItemCls)
                        }
                    }
                }
        		mdiViewPortViewModel.set('currentMenu', Mdi.store.Menu.getRoot().findChild('code', record.get('code'), true));
        		view.fireEvent('openMenu', Mdi.store.Menu.getRoot().findChild('id', record.getId(), true));
        	}
        }
    },
    onLeftMenuAfterRender: function(component, eOpts) {
        var me = this,
            view = me.getView().getView(),
            el;
        Ext.create('Ext.tip.ToolTip', {
            target: view.el,
            delegate: view.itemSelector,
            trackMouse: true,
            renderTo: Ext.getBody(),
            listeners: {
                beforeshow: function(tip) {
                    if (tip.triggerElement.getAttribute('showtip') !== 'true') {
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
        	//el.destroy();
        }
        component.header.el.insertHtml('afterBegin', '<div class="mdi-left-menu-header-left" tabIndex="0"></div>');
        component.header.el.dom.children[0].addEventListener('keydown', function(event) {
            if(event.keyCode === 13) {
                component.collapse();
            }
        });
        var leftCollapseImg = component.header.el.dom.querySelector('img'); 
        leftCollapseImg.setAttribute('alt','LEFT 메뉴 활성화');
        leftCollapseImg.parentNode.setAttribute('title', 'LEFT 메뉴 비활성화');
    },
    onTreepanelBeforeCollapse: function(p, direction, animate, eOpts) {
        var me = this,
            view = me.getView();
        
        if (view.splitter) {
//        	view.splitter.collapseEl.dom.tabIndex = 0;
//        	view.splitter.collapseEl.dom.addEventListener('keydown', function(event) {
//	            if(event.keyCode === 13) {
//	            	view.expand();
//	            }
//	        });
//        	view.splitter.collapseEl.dom.setAttribute('title', 'LEFT 메뉴 활성화');
            view.splitter.setWidth(8);
            view.splitter.setStyle('display', 'block');
        }
        Etna.onDone(function(){
        	//if(view.el.query('img[alt=expand-right-이미지]').length !== 0) {
                view.el.query('img[alt=expand-right-이미지]')[0].setAttribute('alt', 'LEFT 메뉴 활성화');
            //}
        });
    },
    onTreepanelBeforeExpand: function(p, animate, eOpts) {
        var me = this,
            view = me.getView();
        if (view.splitter) {
        	view.splitter.collapseEl.dom.tabIndex = -1;
            view.splitter.setWidth(0);
        }
    },
    onMdiLeftMenuOpenUsingKeyboard: function(tableview, record) {
    	var me = this,
        view = me.getView(),
        mdiViewPortViewModel = this.getView().up('mdiviewport').viewModel;
	    if (!record.isLeaf()) {
	        if (record.isExpanded()) {
	            record.collapse();
	        } else {
	            record.expand();
	        }
	        me.adjustWidth();
	    } else {
	    	if(record.get('code') === 'MEM10420'){
	    		//입찰보증금 미지급 업체관리 메뉴
	          var w = 780,
	          h = 768,
	          leftPosition = (screen.width-w)/2,
	          topPosition = (screen.height-h)/2;
	         // 문서번호 안전(정보)-2363('20.11.6)관련 테스트 ip 주소 대외 노출건 삭제 및 주석처리('20.11.12 신상훈)
	         // 확인결과 해당메뉴 미개발됨(관련문서 자재(구매)-4783('16.9.29)) 
	         // window.open('http://주소삭제/choi/default_list.jsp?p1='+ Cmmn.User.get('username'), 'print', 'location=no, width='+w+',height='+h+',top='+topPosition+',left='+leftPosition+',scrollbars=yes');
	         // window.open('/?p1='+ Cmmn.User.get('username'), 'print', 'location=no, width='+w+',height='+h+',top='+topPosition+',left='+leftPosition+',scrollbars=yes');
	    	}else{
	    		/*
	    		 * 20.01.22 임상근 통합검색 Left Menu 클릭시 breadCrumb에 해당 메뉴 표시되도록 수정,
	    		 * 2 티어 메뉴에서 탭 변경 후 복귀하여 다른 메뉴 클릭하면 기존 메뉴 select가 풀리지 않던 현상 수정
	    		 */
	    		if(record.get('code').indexOf('SEARCH') != -1) {
	                var nodes = tableview.getNodes();
	                for(var i=0; i < nodes.length; i++) {
	                    var node = nodes[i];
	                    if(node.classList.contains(tableview.selectedItemCls)){
	                        node.classList.remove(tableview.selectedItemCls)
	                    }
	                }
	            }
	    		mdiViewPortViewModel.set('currentMenu', Mdi.store.Menu.getRoot().findChild('code', record.get('code'), true));
	    		view.fireEvent('openMenu', Mdi.store.Menu.getRoot().findChild('id', record.getId(), true));
	    	}
	    }
    }
});

/*
 * File: app/view/mdi/Left.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.Left', {
    extend: Ext.tree.Panel,
    alias: 'widget.mdileft',
    controller: 'mdileft',
    viewModel: {
        type: 'mdileft'
    },
    stateId: 'mdi.leftmenu',
    stateful: true,
    border: false,
    height: 250,
    ui: 'mdi-left',
    width: 200,
    collapsedCls: 'mdi-left-menu-collapsed',
    collapsible: true,
    header: {
        cls: 'mdi-left-menu-header'
    },
    iconCls: 'mdi-left-title-icon',
    hideHeaders: true,
    lines: false,
    rootVisible: false,
    bind: {
        store: '{menuStore}'
    },
    viewConfig: {
        border: '0 1 0 0'
    },
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
                return value;
            },
            // if(record.isLeaf()) {
            //     return Ext.String.format('<div class="menu-leaf"><div class="menu-icon">{0}</div></div>', value);
            // }
            // return Ext.String.format('<div class="menu-wrap"><div class="menu-icon">{0}</div></div>', value);
            dataIndex: 'text',
            flex: 1
        }
    ],
    listeners: {
        cellclick: 'onLeftMenuCellClick',
        afterrender: 'onLeftMenuAfterRender',
        beforecollapse: 'onTreepanelBeforeCollapse',
        beforeexpand: 'onTreepanelBeforeExpand',
        keydown: 'onKeyDownEvent'
    },
    plugins: [
        {
            ptype: 'etnagridstateful'
        }
    ],
    applyState: function(state) {
        var me = this;
        me.callParent(arguments);
        if (state.collapsed) {
            me.fireEvent('collapse', me);
        }
        Ext.defer(function() {
            Ext.Array.each(me.columns, function(column, index) {
                column.flex = Mdi.view.mdi.Left.prototype.columns[index].flex;
            });
        }, 10);
    },
    getState: function() {
        var me = this,
            state = me.callParent(arguments);
        Ext.Array.each(state.columns, function(column, index) {
            var prototype = Mdi.view.mdi.Left.prototype,
                width, flex;
            delete column.flex;
            column.width = Mdi.view.mdi.Left.prototype.width;
        });
        return Ext.apply(state, {
            split: Ext.apply(me.split, {
                width: me.splitter.getWidth()
            }),
            width: Mdi.view.mdi.Left.prototype.width
        });
    }
});

/*
 * File: app/view/mdi/MyAppViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.MyAppViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mdimyapp',
    stores: {
        appStoreBreadcrumbStore: {
            type: 'tree',
            model: 'Mdi.model.App',
            proxy: {
                type: 'memory'
            }
        },
        myAppBreadcrumbStore: {
            type: 'tree',
            model: 'Mdi.model.App',
            proxy: {
                type: 'memory'
            }
        },
        appStoreCategoryStore: {
            type: 'tree',
            model: 'Mdi.model.App',
            data: [],
            proxy: {
                type: 'memory'
            }
        },
        myAppCategoryStore: {
            type: 'tree',
            model: 'Mdi.model.App',
            data: [],
            proxy: {
                type: 'memory'
            }
        },
        appStore: {
            type: 'tree',
            model: 'Mdi.model.App',
            root: {},
            proxy: {
                type: 'direct',
                directFn: 'smartsuit.ui.etnajs.cmmn.AppStoreController.getAppStoreApps',
                reader: {
                    type: 'json',
                    transform: {
                        type: 'hierarchy',
                        idProperty: 'id',
                        parentProperty: 'superId',
                        rootId: null,
                        includeRoot: false,
                        interceptor: function(record, level, leaf) {
                            record.leaf = leaf;
                        }
                    }
                }
            },
            listeners: {
                load: 'onAppStoreLoad'
            },
            sorters: {
                property: 'orderNo'
            }
        },
        userAppStore: {
            model: 'Mdi.model.App',
            proxy: {
                type: 'memory'
            }
        },
        userMyAppStore: {
            model: 'Mdi.model.App',
            proxy: {
                type: 'memory'
            }
        },
        myAppStore: {
            type: 'tree',
            autoLoad: true,
            model: 'Mdi.model.App',
            root: {
                loaded: true
            },
            proxy: {
                type: 'direct',
                directFn: 'smartsuit.ui.etnajs.cmmn.AppStoreController.getMyApps',
                reader: {
                    type: 'json',
                    transform: {
                        type: 'hierarchy',
                        idProperty: 'id',
                        parentProperty: 'superId',
                        rootId: null,
                        includeRoot: false,
                        interceptor: function(record, level, leaf) {
                            record.leaf = leaf;
                        }
                    }
                }
            },
            listeners: {
                load: 'onMyAppStoreLoad'
            },
            sorters: {
                property: 'orderNo'
            }
        }
    },
    createMyApps: function(superId, apps) {
        var me = this,
            deferred = Ext.create('Deft.Deferred');
        smartsuit.ui.etnajs.cmmn.AppStoreController.createMyApps(apps, function(result, e) {
            if (e.status) {
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });
        return deferred.promise;
    },
    createMyApp: function(app) {
        var me = this,
            deferred = Ext.create('Deft.Deferred');
        smartsuit.ui.etnajs.cmmn.AppStoreController.createMyApp(app, function(result, e) {
            if (e.status) {
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });
        return deferred.promise;
    },
    createAppId: function() {
        return new Ext.data.identifier.Uuid().generate();
    },
    deleteMyApp: function(app) {
        var me = this,
            deferred = Ext.create('Deft.Deferred');
        smartsuit.ui.etnajs.cmmn.AppStoreController.deleteMyApp(app, function(result, e) {
            if (e.status) {
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });
        return deferred.promise;
    },
    deleteMyApps: function(apps) {
        var me = this,
            deferred = Ext.create('Deft.Deferred');
        smartsuit.ui.etnajs.cmmn.AppStoreController.deleteMyApps(apps, function(result, e) {
            if (e.status) {
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });
        return deferred.promise;
    },
    updateMyApp: function(app) {
        var me = this,
            deferred = Ext.create('Deft.Deferred');
        smartsuit.ui.etnajs.cmmn.AppStoreController.updateMyApp(app, function(result, e) {
            if (e.status) {
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });
        return deferred.promise;
    },
    updateMyApps: function(apps) {
        var me = this,
            deferred = Ext.create('Deft.Deferred');
        smartsuit.ui.etnajs.cmmn.AppStoreController.updateMyApps(apps, function(result, e) {
            if (e.status) {
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });
        return deferred.promise;
    }
});

/*
 * File: app/view/mdi/MyAppViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.MyAppViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mdimyapp',
    onViewChangeButtonClick: function() {
        var me = this,
            view = me.getView(),
            layout = view.getLayout();
        if (layout.getNext()) {
            layout.next();
        } else {
            layout.prev();
        }
        view.header.el.toggleCls('appstore');
    },
    init: function() {
        var me = this;
        me.contextMenu = Ext.create('Ext.menu.Menu', {
            ui: 'app-context',
            items: [
                {
                    text: '#{폴더 생성}',
                    action: 'new',
                    iconCls: 'new'
                },
                {
                    text: '#{이름 바꾸기}',
                    action: 'rename',
                    iconCls: 'rename'
                },
                {
                    text: '#{삭제}',
                    action: 'delete',
                    iconCls: 'delete'
                }
            ],
            listeners: {
                click: me.onContextMenuClick,
                scope: me
            }
        });
        me.getView().loadMask = Ext.create('Ext.LoadMask', {
            target: me.getView(),
            msg: '<div class="' + Ext.baseCSSPrefix + 'appstore-mask-msg-text">Loading...</div>',
            cls: Ext.baseCSSPrefix + 'mask-msg ' + Ext.baseCSSPrefix + 'appstore-mask-msg',
            maskCls: Ext.baseCSSPrefix + 'appstore-mask',
            renderTpl: [
                '<div id="{id}-msgEl" data-ref="msgEl" role="{role}"',
                '<tpl if="ariaAttr"> {ariaAttr}</tpl>',
                ' class="{[values.$comp.msgCls]} ',
                Ext.baseCSSPrefix,
                'mask-msg-inner {childElCls}">',
                '<div id="{id}-msgTextEl" data-ref="msgTextEl" class="',
                Ext.baseCSSPrefix,
                'mask-msg-text ',
                Ext.baseCSSPrefix,
                'appstore-mask-bg',
                '{childElCls}">{msg}</div>',
                '</div>'
            ]
        });
        Ext.defer(function() {
            me.getView().setLoading(true);
        }, 1);
    },
    onContextMenuClick: function(menu, item, e) {
        var me = this,
            vm = me.getViewModel(),
            app = menu.app;
        if (app) {
            if (item.action == 'new') {
                me.createMyApp(app);
            } else if (item.action == 'rename') {
                me.updateMyApp(app);
            } else if (item.action == 'delete') {
                me.deleteMyApp(app, menu.apps);
            }
        }
    },
    createMyApp: function(app) {
        var me = this,
            vm = me.getViewModel(),
            view = me.getView(),
            myAppCategoryPanel = me.lookupReference('myAppCategoryPanel'),
            myAppStore = me.getStore('myAppStore'),
            rootNode = myAppStore.getRootNode(),
            selected = myAppCategoryPanel.getSelection()[0],
            confirm = Ext.Msg.prompt('#{이름 바꾸기}', '#{새 이름을 입력해 주십시오:}', function(button, value) {
                if (button == 'ok') {
                    var orderNo,
                        comparisonFn = function(a, b) {
                            var o1 = a.get('orderNo'),
                                o2 = b.get('orderNo');
                            if (o1 > o2) {
                                return 1;
                            } else if (o1 < o2) {
                                return -1;
                            }
                            return 0;
                        },
                        childNodes;
                    if (selected.isRoot()) {
                        childNodes = rootNode.childNodes;
                        orderNo = childNodes.length > 0 ? (Ext.Array.max(childNodes, comparisonFn).get('orderNo') + 1) : 1;
                    } else {
                        childNodes = rootNode.findChild('id', selected.getId(), true).childNodes;
                        orderNo = childNodes.length > 0 ? (Ext.Array.max(childNodes, comparisonFn).get('orderNo') + 1) : 1;
                    }
                    view.setLoading(true);
                    vm.createMyApp({
                        id: vm.createAppId(),
                        name: value,
                        orderNo: orderNo,
                        superId: app.isRoot() ? null : app.getId()
                    }).always(function() {
                        me.getStore('myAppStore').load();
                    }).done();
                }
            }, me, false, '#{새폴더}');
        confirm.textField.selectText();
    },
    updateMyApp: function(app) {
        var me = this,
            vm = me.getViewModel(),
            view = me.getView(),
            confirm = Ext.Msg.prompt('#{이름 바꾸기}', '#{새 이름을 입력해 주십시오:}', function(button, value) {
                if (button == 'ok') {
                    view.setLoading(true);
                    vm.updateMyApp(Ext.apply(app.getData(), {
                        name: value
                    })).always(function() {
                        me.getStore('myAppStore').load();
                    }).done();
                }
            }, me, false, app.get('name'));
        confirm.textField.selectText();
    },
    deleteMyApp: function(app, apps) {
        var me = this,
            vm = me.getViewModel(),
            view = me.getView(),
            myAppStore = me.getStore('myAppStore'),
            rootNode = myAppStore.getRootNode(),
            isMultiSelect = (apps && apps.length > 1),
            msg = isMultiSelect ? '선택한 {0} 외 {1}개를 삭제하시겠습니까?' : '선택한 {0}를(을) 삭제하시겠습니까?';
        Ext.Msg.confirm('#{삭제}', Ext.String.format(msg, app.get('isFolder') ? '#{폴더}' : '#{앱}', isMultiSelect ? apps.length - 1 : 0), function(button) {
            if (button == 'yes') {
                me.myAppDeleted = true;
                view.setLoading(true);
                if (app.isRoot()) {
                    apps = [];
                    rootNode.eachChild(function(node) {
                        apps.push({
                            id: node.getId()
                        });
                    });
                    vm.deleteMyApps(apps).always(function() {
                        myAppStore.load();
                    }).done();
                } else {
                    var updateApps = [],
                        sortedApps = Ext.Array.sort(app.parentNode.childNodes, function(n1, n2) {
                            if (n1.get('orderNo') > n2.get('orderNo')) {
                                return 1;
                            } else if (n1.get('orderNo') < n2.get('orderNo')) {
                                return -1;
                            } else {
                                return 0;
                            }
                        }),
                        orderNo = 0,
                        deleteApps;
                    if (isMultiSelect) {
                        deleteApps = [];
                        Ext.Array.each(sortedApps, function(node) {
                            if (!Ext.Array.contains(apps, node)) {
                                orderNo++;
                                if (node.get('orderNo') != orderNo) {
                                    updateApps.push(Ext.apply(node.getData(), {
                                        orderNo: orderNo
                                    }));
                                }
                            }
                        });
                        Ext.Array.each(apps, function(app) {
                            deleteApps.push({
                                id: app.getId()
                            });
                        });
                        vm.deleteMyApps(deleteApps);
                    } else {
                        Ext.Array.each(sortedApps, function(node) {
                            if (node.getId() != app.getId()) {
                                orderNo++;
                                if (node.get('orderNo') != orderNo) {
                                    updateApps.push(Ext.apply(node.getData(), {
                                        orderNo: orderNo
                                    }));
                                }
                            }
                        });
                        vm.deleteMyApp({
                            id: app.getId()
                        });
                    }
                    vm.updateMyApps(updateApps).always(function() {
                        myAppStore.load();
                    }).done();
                }
            }
        }, me);
    },
    deleteMyApps: function(apps, app) {
        var me = this,
            vm = me.getViewModel(),
            view = me.getView(),
            myAppStore = me.getStore('myAppStore'),
            rootNode = myAppStore.getRootNode(),
            deleteApps = [];
        me.myAppDeleted = true;
        view.setLoading(true);
        Ext.Array.each(apps, function(app) {
            deleteApps.push({
                id: app.getId()
            });
        });
        var app = apps[0],
            name = app.get('name'),
            count = apps.length;
        vm.deleteMyApps(deleteApps).always(function() {
            myAppStore.load();
            Etna.Message.alert(Ext.String.format('{0} {1}앱의 권한이 없어 삭제되었습니다.', name, count > 1 ? ' 외 ' + (count - 1) + '개의 ' : ''));
        });
    },
    onUpdateButtonClick: function() {
        var me = this,
            view = me.getView(),
            layout = me.getView().getLayout(),
            activeItem = layout.getActiveItem();
        view.setLoading(true);
        if (activeItem.reference == 'myapp') {
            me.getStore('myAppStore').load();
        } else {
            me.getStore('appStore').load();
        }
    },
    breadcrumbSelectionChange: function(node, activePanel) {
        var me = this,
            rootNode = activePanel.getStore().getRootNode();
        if (node) {
            activePanel.getSelectionModel().select(node.isRoot() ? rootNode : (function() {
                var retVal = rootNode.findChild('id', node.getId(), true);
                retVal.parentNode.expand();
                return retVal;
            }()));
        }
    },
    categorySelectionChange: function(activeContainer, selection) {
        var me = this,
            treepanel = activeContainer.down('treepanel'),
            selectionModel = treepanel.getSelectionModel(),
            breadcrumb = activeContainer.down('breadcrumb'),
            breadcrumbStore = breadcrumb.getStore(),
            dataview = activeContainer.down('dataview[dataview=true]');
        if (selection) {
            selection = breadcrumbStore.getNodeById(selection.getId());
            breadcrumb.setSelection(selection);
        } else {
            selection = selectionModel.getLastSelected();
            selectionModel.select(selection);
        }
        dataview.getSelectionModel().deselectAll();
        dataview.refresh();
    },
    dataviewItemDbClick: function(activeContainer, appId) {
        var me = this,
            dataview = activeContainer.down('dataview[dataview=true]'),
            treepanel = activeContainer.down('treepanel'),
            rootNode = treepanel.getRootNode(),
            node = rootNode.findChild('id', appId, true);
        if (node && !node.isLeaf()) {
            node.expand();
            treepanel.getSelectionModel().select(node);
        }
        dataview.getSelectionModel().deselectAll();
    },
    categoryPanelToggle: function(button) {
        var me = this,
            view = me.getView(),
            activeItem = view.getLayout().getActiveItem(),
            treepanel = activeItem.down('treepanel'),
            splitter = activeItem.down('splitter');
        treepanel.toggleCollapse();
        button.el.toggleCls('collapsed');
        splitter.setVisible(!splitter.isVisible());
    },
    onViewRender: function(component, eOpts) {
        var me = this,
            view = component,
            vm = me.getViewModel(),
            myAppStore = me.getStore('myAppStore'),
            rootNode = myAppStore.getRootNode(),
            findAppById = function(id) {
                return rootNode.findChild('id', id, true);
            };
        me.categoryDragZone = new Ext.dd.DragZone(view.el, {
            view: view,
            animRepair: false,
            ddGroup: 'myapp',
            proxy: new Ext.dd.StatusProxy({
                id: view.el.id + '-drag-status-proxy',
                animRepair: false,
                cls: 'app-category-dd-drag-proxy',
                renderTpl: [
                    '<div class="' + Ext.baseCSSPrefix + 'dd-drag-ghost" role="presentation">',
                    '<div id="{id}-ghost" data-ref="ghost" role="presentation"></div>',
                    '<div class="' + Ext.baseCSSPrefix + 'dd-drop-wrap ' + Ext.baseCSSPrefix + 'dd-drop-wrap-hidden">',
                    '<div class="' + Ext.baseCSSPrefix + 'dd-drop-icon" role="presentation"></div>',
                    '<div class="' + Ext.baseCSSPrefix + 'dd-drop-text" role="presentation"></div>',
                    '</div>',
                    '</div>'
                ]
            }),
            getDragData: function(e) {
                var self = this,
                    sourceEl = e.getTarget('.x-grid-cell-inner', 10),
                    recordEl = e.getTarget(view.itemSelector, 10),
                    ddel;
                if (sourceEl) {
                    ddel = sourceEl.cloneNode(true);
                    ddel.id = Ext.id();
                    return {
                        ddel: ddel,
                        sourceEl: sourceEl,
                        repairXY: Ext.fly(sourceEl).getXY(),
                        record: view.getRecord(recordEl)
                    };
                }
            },
            getRepairXY: function() {
                return this.dragData.repairXY;
            },
            afterRepair: function() {
                var self = this;
                self.dragging = false;
            }
        });
        me.categoryDropZone = new Ext.dd.DropZone(view.el, {
            view: view,
            ddGroup: 'myapp',
            containerScroll: true,
            getTargetFromEvent: function(e) {
                return e.getTarget(view.itemSelector);
            },
            onNodeEnter: function(target, dd, e, data) {
                var self = this,
                    sourceRecord = dd.dragData.record,
                    targetRecord = view.getRecord(target),
                    sourceApp = sourceRecord.isRoot() ? rootNode : findAppById(sourceRecord.getId()),
                    targetApp = targetRecord.isRoot() ? rootNode : findAppById(targetRecord.getId()),
                    proxyEl = Ext.get(dd.dragElId),
                    wrapEl = proxyEl.down('.x-dd-drop-wrap'),
                    textEl = proxyEl.down('.x-dd-drop-text');
                wrapEl.addCls('x-dd-drop-wrap-show');
                 if (sourceApp.isRoot() || targetApp.getId() == sourceApp.getId() || sourceApp.parentNode.getId() == targetApp.getId() || sourceApp.findChild('id', targetApp.getId(), true)) {
                    dd.dragStatus = self.dropNotAllowed;
                    textEl.dom.innerHTML = Ext.String.format('{0}으(로) 이동할 수 없습니다', targetRecord.get('name'));
                } else {
                    textEl.dom.innerHTML = Ext.String.format('{0}으(로) 이동', targetRecord.get('name'));
                    dd.dragStatus = self.dropAllowed;
                }
            },
            onNodeOver: function(target, dd, e, data) {
                return dd.dragStatus;
            },
            onNodeOut: function(target, dd, e, data) {
                var proxyEl = Ext.get(dd.dragElId),
                    wrapEl = proxyEl.down('.x-dd-drop-wrap');
                wrapEl.removeCls('x-dd-drop-wrap-show');
            },
            onNodeDrop: function(target, dd, e, data) {
                var self = this,
                    sourceRecord = dd.dragData.record,
                    targetRecord = view.getRecord(target),
                    orderNo = 1,
                    sourceApp, targetApp, selectedApps, updateApps;
                if (dd.proxy.dropStatus == self.dropAllowed) {
                    sourceApp = findAppById(sourceRecord.getId());
                    targetApp = targetRecord.isRoot() ? rootNode : findAppById(targetRecord.getId());
                    selectedApps = [
                        sourceApp.getId()
                    ];
                    updateApps = [
                        Ext.apply(sourceRecord.getData(), {
                            superId: targetApp.isRoot() ? null : targetApp.getId(),
                            orderNo: targetApp.childNodes.length + 1
                        })
                    ];
                    if (!dd.view.isTreeView) {
                        Ext.Array.each(dd.view.el.query('.' + dd.view.selectedItemCls), function(el) {
                            var appId = el.hasAttribute('app-id') ? el.getAttribute('app-id') : view.getRecord(el).getId();
                            if (!Ext.Array.contains(selectedApps, appId)) {
                                selectedApps.push(appId);
                                var app = findAppById(appId);
                                updateApps.push(Ext.apply(app.getData(), {
                                    superId: targetApp.isRoot() ? null : targetApp.getId(),
                                    orderNo: targetApp.childNodes.length + 1
                                }));
                            }
                        });
                    }
                    Ext.Array.each(sourceApp.parentNode.childNodes, function(app) {
                        if (!Ext.Array.contains(selectedApps, app.getId())) {
                            if (app.get('orderNo') != orderNo) {
                                updateApps.push(Ext.apply(app.getData(), {
                                    orderNo: orderNo
                                }));
                            }
                            orderNo++;
                        }
                    });
                    me.getView().setLoading(true);
                    me.getViewModel().updateMyApps(updateApps).always(function() {
                        me.getView().setLoading(true);
                        myAppStore.load({
                            callback: function() {}
                        });
                    });
                }
            }
        });
    },
    //view.select(view.el.down('[app-id="' + sourceApp.getId() + '"]'));
    onMyAppCategoryPanelExpand: function(p, eOpts) {
        p.getView().refresh();
    },
    onMyAppCategoryPanelSelectionChange: function(model, selected, eOpts) {
        var me = this,
            myappContainer = me.lookupReference('myapp');
        me.categorySelectionChange(myappContainer, selected[0]);
    },
    onMyAppCategoryPanelContainerContextMenu: function(dataview, e, eOpts) {
        e.preventDefault();
    },
    onMyAppCategoryPanelItemContextMenu: function(dataview, record, item, index, e, eOpts) {
        var me = this;
        e.preventDefault();
        me.contextMenu.app = record;
        me.contextMenu.showAt(e.getX(), e.getY());
        Ext.Array.each(me.contextMenu.query('[action]'), function(menu) {
            if (menu.action == 'rename') {
                menu.setVisible(!record.isRoot());
            } else {
                menu.setVisible(true);
            }
        });
    },
    onMyAppToggleButtonClick: function(button, e, eOpts) {
        var me = this;
        me.categoryPanelToggle(button);
    },
    onMyAppBreadcrumbSelectionChange: function(breadcrumb, node, eOpts) {
        var me = this,
            view = me.getView(),
            activeItem = view.getLayout().getActiveItem(),
            treepanel = activeItem.down('treepanel');
        me.breadcrumbSelectionChange(node, treepanel);
    },
    onMyAppViewItemDbClick: function(dataview, record, item, index, e, eOpts) {
        var me = this,
            view = me.getView(),
            myAppStore = me.getStore('myAppStore'),
            rootNode = myAppStore.getRootNode(),
            node = rootNode.findChild('id', item.getAttribute('app-id'), true),
            classpath, authKey, activeContainer;
        if (node && !node.isFolder() && node.isLeaf()) {
            classpath = node.get('classpath');
            authKey = node.get('code');
            if (e.ctrlKey) {
                var url = Ext.String.format('app.do?classpath={0}', classpath);
                var body = Ext.getBody();
                var options = Ext.String.format('width={0},height={1},menubar=0,status=0,toolbar=0,location=0', body.getWidth() * 0.9, body.getHeight() * 0.9);
                var w = window.open(url, '_blank', options);
                Ext.defer(function() {
                    w.focus();
                }, 500);
            } else {
                if (MdiManager.hasView(classpath)) {
                    MdiManager.showView(classpath);
                } else {
                    MdiManager.addView(classpath, {
                        title: node.get('name'),
                        authKey: authKey
                    }, node.get('requireClass'));
                }
            }
            me.getView().close();
        } else {
            activeContainer = view.getLayout().getActiveItem();
            me.dataviewItemDbClick(activeContainer, item.getAttribute('app-id'));
        }
    },
    onMyAppViewContainerContextMenu: function(dataview, e, eOpts) {
        var me = this;
        app = me.lookupReference('myAppCategoryPanel').getSelectionModel().getSelection()[0];
        e.preventDefault();
        me.contextMenu.app = app;
        me.contextMenu.showAt(e.getX(), e.getY());
        Ext.Array.each(me.contextMenu.query('[action]'), function(menu) {
            if (menu.action == 'new') {
                menu.setVisible(true);
            } else {
                menu.setVisible(false);
            }
        });
    },
    onMyAppViewItemContextMenu: function(dataview, record, item, index, e, eOpts) {
        var me = this;
        store = me.getStore('myAppStore') , rootNode = store.getRootNode() , selectedItems = dataview.el.query('.' + dataview.selectedItemCls) , apps = [];
        e.preventDefault();
        Ext.Array.each(selectedItems, function(selectedItem) {
            apps.push(rootNode.findChild('id', selectedItem.getAttribute('app-id'), true));
        });
        me.contextMenu.apps = apps;
        me.contextMenu.app = rootNode.findChild('id', item.getAttribute('app-id'), true);
        me.contextMenu.showAt(e.getX(), e.getY());
        Ext.Array.each(me.contextMenu.query('[action]'), function(menu) {
            if (menu.action == 'new' || (menu.action == 'rename' && !me.contextMenu.app.isFolder())) {
                menu.setVisible(false);
            } else {
                menu.setVisible(true);
            }
        });
    },
    onMyAppViewRender: function(component, eOpts) {
        var me = this,
            view = component,
            vm = me.getViewModel(),
            myAppStore = me.getStore('myAppStore'),
            rootNode = myAppStore.getRootNode(),
            findAppById = function(id) {
                return rootNode.findChild('id', id, true);
            };
        me.dragZone = new Ext.dd.DragZone(view.el, {
            view: view,
            animRepair: false,
            ddGroup: 'myapp',
            proxy: new Ext.dd.StatusProxy({
                id: view.el.id + '-drag-status-proxy',
                animRepair: false,
                cls: 'myapp-dd-drag-proxy',
                renderTpl: [
                    '<div class="' + Ext.baseCSSPrefix + 'dd-drag-ghost" role="presentation">',
                    '<div id="{id}-ghost" data-ref="ghost" role="presentation"></div>',
                    '<div class="' + Ext.baseCSSPrefix + 'dd-drop-wrap ' + Ext.baseCSSPrefix + 'dd-drop-wrap-hidden">',
                    '<div class="' + Ext.baseCSSPrefix + 'dd-drop-icon" role="presentation"></div>',
                    '<div class="' + Ext.baseCSSPrefix + 'dd-drop-text" role="presentation"></div>',
                    '</div>',
                    '</div>'
                ]
            }),
            getDragData: function(e) {
                var self = this,
                    sourceEl = e.getTarget(view.itemSelector, 10),
                    appId, ddel;
                if (sourceEl) {
                    appId = sourceEl.getAttribute('app-id');
                    ddel = sourceEl.cloneNode(true);
                    ddel.id = Ext.id();
                    return {
                        ddel: ddel,
                        sourceEl: sourceEl,
                        repairXY: Ext.fly(sourceEl).getXY(),
                        record: view.dataSource.findRecord('id', appId),
                        items: view.el.query('.myapp-dataview-item')
                    };
                }
            },
            getRepairXY: function() {
                return this.dragData.repairXY;
            },
            afterRepair: function() {
                var self = this,
                    indicator = this.view.el.down('.myapp-dataview-indicator');
                self.dragging = false;
                indicator.dom.removeAttribute('app-id');
                indicator.dom.removeAttribute('align');
                indicator.setVisible(false);
            }
        });
        me.dropZone = new Ext.dd.DropZone(view.el, {
            view: view,
            ddGroup: 'myapp',
            containerScroll: true,
            getTargetFromEvent: function(e) {
                return e.getTarget(view.itemSelector);
            },
            onNodeEnter: function(target, dd, e, data) {
                var self = this,
                    sourceEl = Ext.get(data.sourceEl),
                    targetEl = Ext.get(target),
                    proxyEl = Ext.get(dd.dragElId),
                    wrapEl = proxyEl.down('.x-dd-drop-wrap'),
                    textEl = proxyEl.down('.x-dd-drop-text'),
                    sourceRecord = dd.dragData.record,
                    sourceApp = sourceRecord.isRoot() ? sourceRecord : findAppById(sourceRecord.getId()),
                    targetApp = findAppById(target.getAttribute('app-id')),
                    name = targetApp.get('name'),
                    dropStatus;
                wrapEl.addCls('x-dd-drop-wrap-show');
                if (sourceApp.isRoot() || !targetEl.down('.app-folder') || sourceApp.getId() == targetApp.getId()) {
                    dropStatus = self.dropNotAllowed;
                } else if (sourceEl.hasCls(view.itemCls) && targetApp.parentNode.getId() == sourceApp.getId()) {
                    dropStatus = self.dropNotAllowed;
                } else if (sourceApp.parentNode.getId() == targetApp.getId() || sourceApp.findChild('id', targetApp.getId(), true)) {
                    dropStatus = self.dropNotAllowed;
                }
                dd.dropStatus = dropStatus || self.dropAllowed;
                textEl.dom.innerHTML = Ext.String.format('{0}으(로) 이동{1}', name, dd.dropStatus === self.dropNotAllowed ? '할 수 없습니다' : '');
            },
            onNodeOver: function(target, dd, e, data) {
                var self = this,
                    indicator = view.el.down('.myapp-dataview-indicator');
                indicator.setVisible(false);
                return dd.dropStatus;
            },
            onNodeOut: function(target, dd, e, data) {
                var proxyEl = Ext.get(dd.dragElId),
                    wrapEl = proxyEl.down('.x-dd-drop-wrap');
                wrapEl.removeCls('x-dd-drop-wrap-show');
            },
            onNodeDrop: function(target, dd, e, data) {
                var self = this,
                    sourceEl = Ext.get(data.sourceEl),
                    targetEl = Ext.get(target),
                    targetApp = findAppById(target.getAttribute('app-id')),
                    sourceRecord = dd.dragData.record,
                    sourceApp = findAppById(sourceRecord.getId()),
                    orderNo = 1,
                    selectedEl = view.el.query('.' + view.selectedItemCls),
                    selectedApps, updateApps;
                if (dd.proxy.dropStatus == self.dropNotAllowed || !targetEl.down('.app-folder')) {
                    return;
                }
                selectedApps = [
                    sourceApp.getId()
                ];
                updateApps = [
                    Ext.apply(sourceApp.getData(), {
                        superId: targetApp.getId(),
                        orderNo: targetApp.childNodes.length + 1
                    })
                ];
                Ext.Array.each(selectedEl, function(el) {
                    var appId = el.getAttribute('app-id');
                    if (!Ext.Array.contains(selectedApps, appId)) {
                        selectedApps.push(appId);
                        var app = findAppById(appId);
                        updateApps.push(Ext.apply(app.getData(), {
                            superId: targetApp.getId(),
                            orderNo: targetApp.childNodes.length + 1
                        }));
                    }
                });
                Ext.Array.each(sourceApp.parentNode.childNodes, function(app) {
                    if (!Ext.Array.contains(selectedApps, app.getId())) {
                        if (app.get('orderNo') != orderNo) {
                            updateApps.push(Ext.apply(app.getData(), {
                                orderNo: orderNo
                            }));
                        }
                        orderNo++;
                    }
                });
                me.getView().setLoading(true);
                vm.updateMyApps(updateApps).always(function() {
                    me.getView().setLoading(true);
                    myAppStore.load();
                });
            },
            onContainerOver: function(source, e, data) {
                var self = this,
                    sourceEl = Ext.get(data.sourceEl),
                    myappBreadcrumb = me.lookupReference('myAppBreadcrumb'),
                    targetRecord = myappBreadcrumb.getSelection(),
                    sourceRecord = source.dragData.record,
                    targetApp = targetRecord.isRoot() ? targetRecord : findAppById(targetRecord.getId()),
                    sourceApp = sourceRecord.isRoot() ? sourceRecord : findAppById(sourceRecord.getId()),
                    indicator, viewTop, viewLeft, viewRight, items, proxyEl, wrapEl, textEl, name;
                if (sourceEl.hasCls(view.itemCls)) {
                    indicator = view.el.down('.myapp-dataview-indicator');
                    viewTop = view.el.getTop();
                    viewLeft = view.el.getLeft();
                    viewRight = view.el.getRight();
                    items = source.dragData.items;
                    for (var i = 0,
                        len = items.length; i < len; i++) {
                        var item = Ext.get(items[i]),
                            itemTop = item.getTop(),
                            itemLeft = item.getLeft(),
                            itemRight = item.getRight(),
                            itemBottom = item.getBottom();
                        if (itemTop < e.getY() && e.getY() < itemBottom && itemLeft - 10 <= e.getX() && itemRight + 10 >= e.getX()) {
                            indicator.setTop(itemTop + 20 - viewTop);
                            indicator.setVisible(true);
                            indicator.dom.setAttribute('app-id', item.getAttribute('app-id'));
                            if (itemLeft > e.getX()) {
                                indicator.dom.setAttribute('align', 'left');
                                indicator.setLeft(itemLeft - 10 - viewLeft);
                            } else {
                                indicator.dom.setAttribute('align', 'right');
                                indicator.setLeft(itemRight + 10 - viewLeft);
                            }
                            return self.dropAllowed;
                        }
                    }
                    indicator.setVisible(false);
                    return self.dropNotAllowed;
                }
                proxyEl = source.proxy.el;
                wrapEl = proxyEl.down('.x-dd-drop-wrap');
                textEl = proxyEl.down('.x-dd-drop-text');
                name = targetRecord.get('name');
                wrapEl.addCls('x-dd-drop-wrap-show');
                if (sourceApp.isRoot() || sourceApp.parentNode.getId() == targetApp.getId() || sourceApp.getId() == targetApp.getId() || sourceApp.findChild('id', targetApp.getId(), true)) {
                    textEl.dom.innerHTML = Ext.String.format('{0}으(로) 이동할 수 없습니다', name);
                    return self.dropNotAllowed;
                }
                textEl.dom.innerHTML = Ext.String.format('{0}으(로) 이동', name);
                return self.dropAllowed;
            },
            onContainerDrop: function(source, e, data) {
                var self = this,
                    sourceEl = Ext.get(data.sourceEl),
                    myappBreadcrumb = me.lookupReference('myAppBreadcrumb'),
                    callback = function() {
                        me.getView().setLoading(true);
                        myAppStore.load({
                            callback: function() {
                                view.select(view.el.down('[app-id="' + sourceApp.getId() + '"]'));
                            }
                        });
                    },
                    targetRecord, targetApp, sourceRecord, sourceApp, updateApps, targetEl, dropAlign, dropAppId, indicator, orderNo;
                if (source.proxy.dropStatus == self.dropNotAllowed) {
                    return;
                }
                sourceRecord = source.dragData.record;
                sourceApp = findAppById(sourceRecord.getId());
                targetRecord = myappBreadcrumb.getSelection();
                targetApp = targetRecord.isRoot() ? rootNode : findAppById(targetRecord.getId());
                updateApps = [];
                if (sourceEl.hasCls(view.itemCls)) {
                    indicator = view.el.down('.myapp-dataview-indicator');
                    if (indicator.dom.hasAttribute('app-id')) {
                        me.getView().setLoading(true);
                        dropAppId = indicator.dom.getAttribute('app-id');
                        dropAlign = indicator.dom.getAttribute('align');
                        targetEl = view.el.down('.myapp-dataview-item[app-id="' + dropAppId + '"]');
                        targetEl.insertSibling(sourceEl, dropAlign == 'right' ? 'after' : 'before');
                        Ext.Array.each(view.el.query('.myapp-dataview-item'), function(appEl, idx) {
                            var app = findAppById(appEl.getAttribute('app-id'));
                            if (app.get('orderNo') != (idx + 1)) {
                                updateApps.push(Ext.apply(app.getData(), {
                                    orderNo: idx + 1
                                }));
                            }
                        });
                        if (updateApps.length > 0) {
                            vm.updateMyApps(updateApps).always(callback);
                        }
                    }
                    indicator.setVisible(false);
                } else {
                    orderNo = 1;
                    Ext.Array.each(sourceApp.parentNode.childNodes, function(app) {
                        if (app.getId() != sourceApp.getId()) {
                            if (app.get('orderNo') != orderNo) {
                                updateApps.push(Ext.apply(app.getData(), {
                                    orderNo: orderNo
                                }));
                            }
                            orderNo++;
                        }
                    });
                    me.getView().setLoading(true);
                    updateApps.push(Ext.apply(sourceApp.getData(), {
                        superId: targetApp.isRoot() ? null : targetApp.getId(),
                        orderNo: targetApp.childNodes.length + 1
                    }));
                    if (updateApps.length > 0) {
                        vm.updateMyApps(updateApps).always(callback);
                    }
                }
            }
        });
    },
    onMyAppViewItemMouseDown: function(dataview, record, item, index, e, eOpts) {
        var selectionModel = dataview.getSelectionModel();
        if (e.button == 2 && !selectionModel.isSelected(record)) {
            selectionModel.select(record);
        }
    },
    onMyAppViewAfterRender: function(component, eOpts) {
        var me = this,
            tpl = component.getTpl('tpl'),
            myAppStore = me.getStore('myAppStore'),
            rootNode = myAppStore.getRootNode();
        Ext.apply(tpl, {
            textMeasureEl: me.textMeasureEl,
            getSelectedNode: function() {
                var selected = me.lookupReference('myAppCategoryPanel').getSelection()[0];
                return selected.isRoot() ? rootNode : rootNode.findChild('id', selected.getId(), true);
            }
        });
        component.tooltip = Ext.create('Ext.tip.ToolTip', {
            target: component.el,
            delegate: component.itemSelector,
            trackMouse: true,
            renderTo: Ext.getBody(),
            listeners: {
                beforeshow: function(tip) {
                    tip.update(rootNode.findChild('id', tip.triggerElement.getAttribute('app-id'), true).get('name'));
                }
            }
        });
    },
    onMyAppViewBeforeDestroy: function(component, eOpts) {
        component.tooltip.destroy();
    },
    onMyAppActivate: function(component, eOpts) {
        var me = this,
            view = me.getView();
        view.setTitle(Ext.String.format('{0}', '마이앱'));
        me.lookupReference('viewChangeButton').setText(Ext.String.format('{0}', '#{앱스토어}'));
        me.lookupReference('myAppCategoryPanel').view.refresh();
        if (me.myAppInstalled) {
            view.setLoading(true);
            me.getStore('myAppStore').load();
            me.myAppInstalled = false;
        }
    },
    onAppStoreCategoryPanelSelectionChange: function(model, selected, eOpts) {
        var me = this,
            appstoreContainer = me.lookupReference('appstore');
        me.categorySelectionChange(appstoreContainer, selected[0]);
    },
    onAppStoreCategoryPanelExpand: function(p, eOpts) {
        p.getView().refresh();
    },
    onAppStoreToggleButtonClick: function(button, e, eOpts) {
        var me = this;
        me.categoryPanelToggle(button);
    },
    onAppStoreBreadcrumbSelectionChange: function(breadcrumb, node, eOpts) {
        var me = this,
            view = me.getView(),
            activeItem = view.getLayout().getActiveItem(),
            treepanel = activeItem.down('treepanel');
        me.breadcrumbSelectionChange(node, treepanel);
    },
    onAppStoreViewItemClick: function(dataview, record, item, index, e, eOpts) {
        var me = this,
            target = e.getTarget('.appstore-install'),
            appStore, rootNode, app, myAppStore, myAppCategoryPanel, myAppCategoryRootNode, selected, orderNo;
        if (!target) {
            return;
        }
        appStore = me.getStore('appStore');
        appStoreRootNode = appStore.getRootNode();
        app = appStoreRootNode.findChild('id', item.getAttribute('app-id'), true);
        myAppStore = me.getStore('myAppStore');
        myAppStoreRootNode = myAppStore.getRootNode();
        myAppCategoryPanel = me.lookupReference('myAppCategoryPanel');
        myAppCategoryRootNode = myAppCategoryPanel.getStore().getRootNode();
        selected = myAppCategoryPanel.getSelection()[0];
        if (app) {
            var item = Ext.get(item),
                pb = item.down('.appstore-progress'),
                cp = pb.down('.cp'),
                keyframes = {},
                percents = [],
                totalPercent = 0,
                vm = me.getViewModel(),
                superId = selected.isRoot() ? null : selected.getId(),
                target = Ext.get(target),
                map = {},
                apps = [],
                callback = function() {
                    if (pb.isVisible()) {
                        Ext.defer(arguments.callee, 10, me);
                        return;
                    }
                    dataview.refreshView();
                };
            for (var i = 0; i < 25; i++) {
                percents[i] = Math.round(Math.random() * 10);
                totalPercent += percents[i];
            }
            for (var i = 0,
                f = 0,
                width = 0; i < 25; i++ , f += 4) {
                width += percents[i] / totalPercent * 130;
                keyframes[f] = {
                    width: width
                };
            }
            cp.animate({
                duration: 2000,
                //keyframes : keyframes,
                to: {
                    width: '100%'
                },
                listeners: {
                    beforeanimate: function() {
                        pb.setVisible(true);
                        target.addCls('install');
                        target.prev().addCls('install');
                        target.down('.text').dom.innerHTML = Ext.String.format('{0}', '#{설치중...}');
                    },
                    afteranimate: function() {
                        pb.setVisible(false);
                        target.removeCls('install');
                        target.prev().removeCls('install');
                        target.down('.text').dom.innerHTML = Ext.String.format('{0}', '#{설치}');
                    }
                }
            });
            var comparisonFn = function(a, b) {
                    var o1 = a.get('orderNo'),
                        o2 = b.get('orderNo');
                    if (o1 > o2) {
                        return 1;
                    } else if (o1 < o2) {
                        return -1;
                    }
                    return 0;
                },
                childNodes;
            if (selected.isRoot()) {
                childNodes = myAppStoreRootNode.childNodes;
                orderNo = childNodes.length > 0 ? (Ext.Array.max(childNodes, comparisonFn).get('orderNo') + 1) : 1;
                myAppStoreRootNode.appendChild(app.clone());
            } else {
                var selectedApp = me.getStore('userMyAppStore').findRecord('id', selected.getId());
                childNodes = selectedApp.childNodes;
                orderNo = childNodes.length > 0 ? (Ext.Array.max(childNodes, comparisonFn).get('orderNo') + 1) : 1;
                selectedApp.appendChild(app.clone());
            }
            map[app.getId()] = {
                id: vm.createAppId(),
                superId: superId,
                appId: app.getId(),
                name: app.get('name'),
                orderNo: orderNo
            };
            apps.push(map[app.getId()]);
            app.cascadeBy(function(node) {
                if (node == app) {
                    return;
                }
                var pNode = map[node.parentNode.getId()];
                map[node.getId()] = {
                    id: vm.createAppId(),
                    superId: pNode.id,
                    appId: node.id,
                    name: node.get('name'),
                    orderNo: node.get('orderNo')
                };
                apps.push(map[node.getId()]);
            });
            me.myAppInstalled = true;
            vm.createMyApps(superId, apps).always(function() {
                app.cascadeBy(function(node) {
                    if (node.isFolder()) {
                        return;
                    } else {
                        node.set('installed', true, {
                            silent: true
                        });
                    }
                });
                callback();
            });
        }
    },
    onAppStoreViewItemDbClick: function(dataview, record, item, index, e, eOpts) {
        var me = this,
            treepanel = me.lookupReference('appStoreCategoryPanel'),
            rootNode = treepanel.getRootNode(),
            node = rootNode.findChild('id', item.getAttribute('app-id'), true);
        if (node && !node.isLeaf() && !e.getTarget('.appstore-install')) {
            node.parentNode.expand();
            treepanel.getSelectionModel().select(node);
        }
    },
    onAppStoreViewAfterRender: function(component, eOpts) {
        var me = this,
            tpl = component.getTpl('tpl'),
            appStore = me.getStore('appStore');
        Ext.apply(tpl, {
            textMeasureEl: me.textMeasureEl,
            getSelectedNode: function() {
                var root = appStore.getRootNode();
                var selected = me.lookupReference('appStoreCategoryPanel').getSelection()[0];
                return selected.isRoot() ? root : root.findChild('id', selected.getId(), true);
            }
        });
    },
    onAppStoreActivate: function(component, eOpts) {
        var me = this,
            view = me.getView(),
            myAppStore = me.getStore('myAppStore'),
            myAppRootNode = myAppStore.getRootNode(),
            appStoreView = me.lookupReference('appStoreView');
        view.setTitle(Ext.String.format('{0}', '앱스토어'));
        me.lookupReference('viewChangeButton').setText(Ext.String.format('{0}', '#{마이앱}'));
        me.lookupReference('appStoreCategoryPanel').getView().refresh();
        if (me.myAppDeleted) {
            me.myAppDeleted = false;
            appStoreView.dataSource.each(function(app) {
                if (myAppRootNode.findChild('appId', app.getId(), true)) {
                    app.set('installed', true, {
                        silent: true
                    });
                } else {
                    app.set('installed', false, {
                        silent: true
                    });
                }
            });
            appStoreView.refreshView();
        }
    },
    onAppStoreBoxReady: function(component, width, height, eOpts) {
        var me = this,
            view = me.getView(),
            store = me.getStore('appStore');
        view.setLoading(true);
        store.load();
    },
    onWindowBeforeRender: function(component, eOpts) {
        var me = this;
        Ext.apply(component, {
            header: {
                cls: 'myapp',
                items: [
                    {
                        xtype: 'button',
                        text: '#{새로고침}',
                        ui: 'app-window-header-tool-medium',
                        iconCls: 'app-store-refresh-button',
                        scale: 'medium',
                        listeners: {
                            click: me.onUpdateButtonClick,
                            scope: me
                        }
                    },
                    {
                        xtype: 'component',
                        cls: 'app-window-header-separator'
                    },
                    {
                        xtype: 'button',
                        text: '#{앱스토어}',
                        ui: 'app-window-header-tool-medium',
                        iconCls: 'app-store-toggle-button',
                        scale: 'medium',
                        padding: '0 0 0 10',
                        reference: 'viewChangeButton',
                        listeners: {
                            click: me.onViewChangeButtonClick,
                            scope: me
                        }
                    }
                ]
            }
        });
    },
    onWindowShow: function(component, eOpts) {
        var me = this,
            view = me.getView(),
            activeItem = view.getLayout().getActiveItem(),
            treepanel = activeItem.down('treepanel');
        treepanel.getView().refresh();
    },
    onWindowRender: function(component, eOpts) {
        var me = this;
        me.textMeasureEl = component.el.insertHtml('afterBegin', '<div class="text-measure"></div>', true);
    },
    onAppStoreLoad: function(treestore, records, successful, operation, node, eOpts) {
        var me = this,
            vm = me.getViewModel(),
            myAppStore = me.getStore('myAppStore'),
            myAppRootNode = myAppStore.getRootNode(),
            appStoreCategoryPanel = me.lookupReference('appStoreCategoryPanel'),
            appStoreBreadcrumbStore = vm.getStore('appStoreBreadcrumbStore'),
            appStoreCategoryStore = vm.getStore('appStoreCategoryStore'),
            root = treestore.getRoot(),
            lastSelected = appStoreCategoryPanel.getSelectionModel().getLastSelected();
        if (root) {
            var rootName = Ext.String.format('#{전체}');
            var pops = [
                    'id',
                    'superId',
                    'name'
                ];
            var breadRootNode = Ext.create('Mdi.model.App', Ext.copyTo({
                    expanded: false,
                    leaf: false
                }, root.getData(), pops)),
                treeRootNode = Ext.copyTo({
                    children: [],
                    expanded: false,
                    leaf: false
                }, root.getData(), pops);
            breadRootNode.set('name', rootName);
            treeRootNode.name = rootName;
            var map = {};
            map['b_' + root.getId()] = breadRootNode;
            map['t_' + root.getId()] = treeRootNode;
            root.cascadeBy(function(node) {
                if (root == node) {
                    return;
                }
                var idx = node.parentNode.indexOf(node) + 1;
                node.set('orderNo', idx);
                if (node.isLeaf()) {
                    return;
                }
                var b = map['b_' + node.getId()] = Ext.create('Mdi.model.App', Ext.copyTo({
                        expanded: false,
                        leaf: false
                    }, node.getData(), pops));
                var t = map['t_' + node.getId()] = Ext.copyTo({
                        children: [],
                        expanded: false,
                        leaf: false
                    }, node.getData(), pops);
                var bNode = map['b_' + node.parentNode.getId()];
                bNode.appendChild(b);
                var tNode = map['t_' + node.parentNode.getId()];
                tNode.children.push(t);
            });
            appStoreCategoryStore.setRootVisible(false);
            treeRootNode = appStoreCategoryStore.setRootNode(treeRootNode);
            appStoreCategoryStore.setRootVisible(true);
            treeRootNode.expand();
            appStoreBreadcrumbStore.setRootNode(breadRootNode);
            me.lookupReference('appStoreBreadcrumb').updateStore(appStoreBreadcrumbStore);
            me.lookupReference('appStoreBreadcrumb')._needsSync = true;
            if (lastSelected) {
                var lastSelectedNode;
                do {
                    lastSelectedNode = treeRootNode.findChild('id', lastSelected.getId(), true);
                    if (lastSelectedNode) {
                        var node = lastSelectedNode;
                        while ((node = node.parentNode)) {
                            node.expand();
                        }
                        if (lastSelected.isExpanded()) {
                            lastSelectedNode.expand();
                        }
                        appStoreCategoryPanel.getSelectionModel().select(lastSelectedNode);
                        break;
                    } else {
                        treeRootNode.expand();
                    }
                } while ((lastSelected = lastSelected.parentNode));
            } else {
                treeRootNode.expand();
            }
            var apps = [];
            root.cascadeBy(function(node) {
                if (root == node) {
                    return;
                }
                apps.push(node);
            });
            Ext.Array.each(apps, function(app) {
                if (!app.isFolder() && myAppRootNode.findChild('appId', app.getId(), true)) {
                    app.set('installed', true);
                }
            });
            me.getStore('userAppStore').loadRecords(apps);
        }
        me.getView().setLoading(false);
    },
    onMyAppStoreLoad: function(treestore, records, successful, operation, node, eOpts) {
        var me = this,
            view = me.getView(),
            vm = me.getViewModel(),
            myAppCategoryPanel = me.lookupReference('myAppCategoryPanel'),
            myAppBreadcrumbStore = vm.getStore('myAppBreadcrumbStore'),
            myAppCategoryStore = vm.getStore('myAppCategoryStore'),
            root = treestore.getRoot(),
            lastSelected = myAppCategoryPanel.getSelectionModel().getLastSelected();
        if (root) {
            var rootName = Ext.String.format('#{전체}');
            var pops = [
                    'id',
                    'superId',
                    'name',
                    'orderNo'
                ];
            var breadRootNode = Ext.create('Mdi.model.App', Ext.copyTo({
                    expanded: false,
                    leaf: false
                }, root.getData(), pops)),
                treeRootNode = Ext.copyTo({
                    children: [],
                    expanded: false,
                    leaf: false
                }, root.getData(), pops);
            breadRootNode.set('name', rootName);
            treeRootNode.name = rootName;
            var map = {};
            var deleteApps = [];
            map['b_' + root.getId()] = breadRootNode;
            map['t_' + root.getId()] = treeRootNode;
            root.cascadeBy(function(node) {
                if (!node.isRoot() && !node.hasRole() && node.get('appId')) {
                    deleteApps.push(node);
                    return;
                }
                if (root == node || (!node.isFolder() && node.isLeaf())) {
                    return;
                }
                var b = map['b_' + node.getId()] = Ext.create('Mdi.model.App', Ext.copyTo({
                        expanded: false,
                        leaf: false
                    }, node.getData(), pops));
                var t = map['t_' + node.getId()] = Ext.copyTo({
                        children: [],
                        expanded: false,
                        leaf: false
                    }, node.getData(), pops);
                var bNode = map['b_' + node.parentNode.getId()];
                bNode.appendChild(b);
                var tNode = map['t_' + node.parentNode.getId()];
                tNode.children.push(t);
            });
            if (deleteApps.length > 0) {
                me.deleteMyApps(Ext.Array.sort(deleteApps, function(a, b) {
                    if (a.get('depth') > b.get('depth')) {
                        return -1;
                    } else if (a.get('depth') < b.get('depth')) {
                        return 1;
                    } else {
                        return 0;
                    }
                }));
                return;
            }
            myAppCategoryStore.setRootVisible(false);
            treeRootNode = myAppCategoryStore.setRootNode(treeRootNode);
            myAppCategoryStore.setRootVisible(true);
            myAppBreadcrumbStore.setRootNode(breadRootNode);
            me.lookupReference('myAppBreadcrumb').updateStore(myAppBreadcrumbStore);
            me.lookupReference('myAppBreadcrumb')._needsSync = true;
            if (lastSelected) {
                var lastSelectedNode;
                do {
                    lastSelectedNode = treeRootNode.findChild('id', lastSelected.getId(), true);
                    if (lastSelectedNode) {
                        var node = lastSelectedNode;
                        while ((node = node.parentNode)) {
                            node.expand();
                        }
                        if (lastSelected.isExpanded()) {
                            lastSelectedNode.expand();
                        }
                        myAppCategoryPanel.getSelectionModel().select(lastSelectedNode);
                        break;
                    } else {
                        treeRootNode.expand();
                    }
                } while ((lastSelected = lastSelected.parentNode));
            } else {
                treeRootNode.expand();
            }
            var apps = [];
            root.cascadeBy(function(node) {
                if (root == node || (!node.isRoot() && !node.hasRole() && node.get('appId'))) {
                    return;
                }
                apps.push(node);
            });
            me.getStore('userMyAppStore').loadRecords(apps);
        }
        me.getView().setLoading(false);
    }
});

/*
 * File: app/view/mdi/MyApp.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.MyApp', {
    extend: Ext.window.Window,
    alias: 'widget.mdimyapp',
    controller: 'mdimyapp',
    viewModel: {
        type: 'mdimyapp'
    },
    height: 250,
    ui: 'app-window',
    width: 400,
    layout: 'card',
    closeAction: 'hide',
    title: '#마이앱}',
    titleAlign: 'center',
    modal: true,
    listeners: {
        beforerender: 'onWindowBeforeRender',
        show: 'onWindowShow',
        render: 'onWindowRender'
    },
    initConfig: function(instanceConfig) {
        var me = this,
            config = {
                items: [
                    {
                        xtype: 'container',
                        reference: 'myapp',
                        layout: 'border',
                        items: [
                            me.processMyAppCategoryPanel({
                                xtype: 'treepanel',
                                floatable: false,
                                region: 'west',
                                reference: 'myAppCategoryPanel',
                                margin: '0 0 0 1',
                                ui: 'apptree',
                                width: 200,
                                bodyPadding: '4 0',
                                header: false,
                                hideCollapseTool: true,
                                title: 'My Tree Panel',
                                hideHeaders: true,
                                displayField: 'name',
                                lines: false,
                                bind: {
                                    store: '{myAppCategoryStore}'
                                },
                                viewConfig: {
                                    listeners: {
                                        render: 'onViewRender'
                                    }
                                },
                                listeners: {
                                    expand: 'onMyAppCategoryPanelExpand',
                                    selectionchange: 'onMyAppCategoryPanelSelectionChange',
                                    containercontextmenu: 'onMyAppCategoryPanelContainerContextMenu',
                                    itemcontextmenu: 'onMyAppCategoryPanelItemContextMenu'
                                }
                            }),
                            {
                                xtype: 'panel',
                                flex: 1,
                                region: 'center',
                                autoScroll: true,
                                ui: 'app-panel',
                                layout: 'fit',
                                dockedItems: [
                                    {
                                        xtype: 'toolbar',
                                        dock: 'top',
                                        padding: 0,
                                        ui: 'app-toolbar-top',
                                        layout: {
                                            type: 'hbox',
                                            align: 'stretch'
                                        },
                                        items: [
                                            {
                                                xtype: 'button',
                                                ui: 'appstore-toggle-toolbar-medium',
                                                iconCls: 'app-store-tree-toggle-button',
                                                scale: 'medium',
                                                listeners: {
                                                    click: 'onMyAppToggleButtonClick'
                                                }
                                            },
                                            {
                                                xtype: 'breadcrumb',
                                                displayField: 'name',
                                                flex: 1,
                                                reference: 'myAppBreadcrumb',
                                                layout: {
                                                    type: 'hbox',
                                                    align: 'stretch'
                                                },
                                                bind: {
                                                    store: '{myAppBreadcrumbStore}'
                                                },
                                                listeners: {
                                                    selectionchange: 'onMyAppBreadcrumbSelectionChange'
                                                }
                                            }
                                        ]
                                    }
                                ],
                                items: [
                                    me.processMyAppView({
                                        xtype: 'dataview',
                                        dataview: true,
                                        reference: 'myAppView',
                                        autoScroll: true,
                                        tpl: Ext.create('Ext.XTemplate', '<div class="myapp-dataview-indicator"></div>', '<tpl for=".">', '    <tpl if="this.filter(values)">', '        <div class="myapp-dataview-item" app-id="{id}">', '            <div class="myapp-wrap">', '                <div class="app-icon-wrap {[this.appStyle(values)]}">', '                    <div class="{[this.appIconStyle(values)]}"></div>    ', '                </div>', '                <div class="myapp-title" style="{[this.textAlign(values)]}">{[this.title(values)]}</div>', '            </div>    ', '        </div>    ', '    </tpl>', '</tpl>', {
                                            filter: function(values) {
                                                var node = this.getSelectedNode();
                                                if (node.findChild('id', values.id)) {
                                                    return true;
                                                }
                                                return false;
                                            },
                                            appStyle: function(values) {
                                                var appStyle = values.appStyle;
                                                if (!values.leaf || values.folder) {
                                                    appStyle = 'app-folder';
                                                } else if (!appStyle) {
                                                    appStyle = 'app-round-1';
                                                }
                                                return appStyle;
                                            },
                                            textAlign: function(values) {
                                                if (Ext.util.TextMetrics.measure(this.textMeasureEl, values.name).width > 90) {
                                                    values.textOverflow = true;
                                                    return "text-align:left";
                                                }
                                            },
                                            title: function(values) {
                                                var title = values.name,
                                                    start = 0,
                                                    dotWidth = 0,
                                                    titleWidth;
                                                if (values.textOverflow) {
                                                    titleWidth = Ext.util.TextMetrics.measure(this.textMeasureEl, title).width;
                                                    for (var i = 0,
                                                        len = title.length; i < len; i++) {
                                                        var w = Ext.util.TextMetrics.measure(this.textMeasureEl, title.substring(start, i)).width;
                                                        if (w > (90) - dotWidth) {
                                                            if (start === 0) {
                                                                dotWidth = 12;
                                                                start = i - 1;
                                                            } else {
                                                                title = title.substring(0, i - 1) + '...';
                                                                break;
                                                            }
                                                        }
                                                    }
                                                }
                                                return title;
                                            },
                                            appIconStyle: function(values) {
                                                var appIconStyle = values.appIconStyle;
                                                if (!appIconStyle) {
                                                    appIconStyle = 'app-no-icon';
                                                }
                                                return appIconStyle;
                                            }
                                        }),
                                        itemCls: 'myapp-dataview-item',
                                        itemSelector: 'div.myapp-dataview-item',
                                        overItemCls: 'myapp-dataview-item-over',
                                        selectedItemCls: 'myapp-dataview-item-selected',
                                        bind: {
                                            store: '{userMyAppStore}'
                                        },
                                        listeners: {
                                            itemdblclick: 'onMyAppViewItemDbClick',
                                            containercontextmenu: 'onMyAppViewContainerContextMenu',
                                            itemcontextmenu: 'onMyAppViewItemContextMenu',
                                            render: {
                                                fn: 'onMyAppViewRender',
                                                single: true
                                            },
                                            itemmousedown: 'onMyAppViewItemMouseDown',
                                            afterrender: 'onMyAppViewAfterRender',
                                            beforedestroy: 'onMyAppViewBeforeDestroy'
                                        }
                                    })
                                ]
                            }
                        ],
                        listeners: {
                            activate: 'onMyAppActivate'
                        }
                    },
                    {
                        xtype: 'container',
                        reference: 'appstore',
                        height: 150,
                        layout: 'border',
                        items: [
                            me.processAppStoreCategoryPanel({
                                xtype: 'treepanel',
                                floatable: false,
                                region: 'west',
                                reference: 'appStoreCategoryPanel',
                                margin: '0 0 0 1',
                                ui: 'apptree',
                                width: 200,
                                bodyPadding: '4 0',
                                header: false,
                                hideCollapseTool: true,
                                hideHeaders: true,
                                displayField: 'name',
                                lines: false,
                                bind: {
                                    store: '{appStoreCategoryStore}'
                                },
                                viewConfig: {},
                                listeners: {
                                    selectionchange: 'onAppStoreCategoryPanelSelectionChange',
                                    expand: 'onAppStoreCategoryPanelExpand'
                                }
                            }),
                            {
                                xtype: 'panel',
                                flex: 1,
                                region: 'center',
                                autoScroll: true,
                                ui: 'app-panel',
                                layout: 'fit',
                                dockedItems: [
                                    {
                                        xtype: 'toolbar',
                                        dock: 'top',
                                        padding: 0,
                                        ui: 'app-toolbar-top',
                                        layout: {
                                            type: 'hbox',
                                            align: 'stretch'
                                        },
                                        items: [
                                            {
                                                xtype: 'button',
                                                ui: 'appstore-toggle-toolbar-medium',
                                                iconCls: 'app-store-tree-toggle-button',
                                                scale: 'medium',
                                                listeners: {
                                                    click: 'onAppStoreToggleButtonClick'
                                                }
                                            },
                                            {
                                                xtype: 'breadcrumb',
                                                displayField: 'name',
                                                flex: 1,
                                                reference: 'appStoreBreadcrumb',
                                                layout: {
                                                    type: 'hbox',
                                                    align: 'stretch'
                                                },
                                                bind: {
                                                    store: '{appStoreBreadcrumbStore}'
                                                },
                                                listeners: {
                                                    selectionchange: 'onAppStoreBreadcrumbSelectionChange'
                                                }
                                            }
                                        ]
                                    }
                                ],
                                items: [
                                    {
                                        xtype: 'dataview',
                                        dataview: true,
                                        reference: 'appStoreView',
                                        autoScroll: true,
                                        tpl: Ext.create('Ext.XTemplate', '<tpl for=".">', '    <tpl if="this.filter(values)">', '        <div class="appstore-dataview-item" app-id="{id}">', '            <div class="appstore-wrap">', '                <div class="app-icon-wrap {[this.appStyle(values)]}">', '                    <div class="{appIconStyle}"></div>    ', '                </div>', '            </div>', '            <div class="appstore-title-wrap {[this.installed(values) ? \'installed\' : \'\']}">', '                <div class="appstore-title">{[this.title(values)]}</div>', '                <div class="appstore-progress">', '                    <div class="cp"></div>', '                    <div class="bl"><div class="br"><div class="bc"></div></div></div>', '                </div>', '            </div>', '            <div class="appstore-install {[this.installed(values) ? \'installed\' : \'\']}">', '                <div class="img"></div>', '                <div class="text">{[this.label(values)]}</div>', '            </div>', '            <tpl if="this.installed(values)">', '                <div class="appstore-installed"></div>', '            </tpl>', '        </div>    ', '    </tpl>', '</tpl>', {
                                            filter: function(values) {
                                                var node = this.getSelectedNode();
                                                if (node.findChild('id', values.id)) {
                                                    return true;
                                                }
                                                return false;
                                            },
                                            label: function(values) {
                                            	return Ext.String.format('{0}', (values.leaf && values.installed) ? '#{설치됨}' : '#{설치}');
                                            },
                                            appStyle: function(values) {
                                                if (!values.leaf) {
                                                    return 'app-folder';
                                                }
                                                return values.appStyle;
                                            },
                                            installed: function(values) {
                                                return values.leaf && values.installed;
                                            },
                                            title: function(values) {
                                                var title = values.name,
                                                    titleWidth = Ext.util.TextMetrics.measure(this.textMeasureEl, title).width,
                                                    start = 0,
                                                    dotWidth = 0;
                                                if (titleWidth > 126) {
                                                    for (var i = 0,
                                                        len = title.length; i < len; i++) {
                                                        var w = Ext.util.TextMetrics.measure(this.textMeasureEl, title.substring(start, i)).width;
                                                        if (w > 126 - dotWidth) {
                                                            if (start === 0) {
                                                                dotWidth = 12;
                                                                start = i - 1;
                                                            } else {
                                                                title = title.substring(0, i - 1) + '...';
                                                                break;
                                                            }
                                                        }
                                                    }
                                                }
                                                return title;
                                            }
                                        }),
                                        disableSelection: true,
                                        itemCls: 'appstore-dataview-item',
                                        itemSelector: 'div.appstore-dataview-item',
                                        overItemCls: 'appstore-dataview-item-over',
                                        selectedItemCls: 'app-dataview-item-selected',
                                        bind: {
                                            store: '{userAppStore}'
                                        },
                                        listeners: {
                                            itemclick: 'onAppStoreViewItemClick',
                                            itemdblclick: 'onAppStoreViewItemDbClick',
                                            afterrender: 'onAppStoreViewAfterRender'
                                        }
                                    }
                                ]
                            }
                        ],
                        listeners: {
                            activate: {
                                fn: 'onAppStoreActivate',
                                single: false
                            },
                            boxready: {
                                fn: 'onAppStoreBoxReady',
                                single: true
                            }
                        }
                    }
                ]
            };
        if (instanceConfig) {
            me.getConfigurator().merge(me, config, instanceConfig);
        }
        return me.callParent([
            config
        ]);
    },
    processMyAppCategoryPanel: function(config) {
        config.split = {
            size: 2,
            collapseOnDblClick: false
        };
        return config;
    },
    processMyAppView: function(config) {
        config.selModel = {
            mode: 'MULTI'
        };
        return config;
    },
    processAppStoreCategoryPanel: function(config) {
        config.split = {
            size: 2,
            collapseOnDblClick: false
        };
        return config;
    }
});

/*
 * File: app/view/mdi/ToolsViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.ToolsViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mditools'
});

/*
 * File: app/view/mdi/ToolsViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.ToolsViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mditools',
    init: function() {
    	if(MdiManager.spmain) {
    		this.getView().hide();
    	}
    },
    onLeftMenuButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('leftMenu');
    },
    onTopMenuButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('topMenu');
    },
    onCloseAllButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('closeAll');
    }
});

/*
 * File: app/view/mdi/Tools.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.Tools', {
    extend: Ext.toolbar.Toolbar,
    alias: 'widget.mditools',
    controller: 'mditools',
    viewModel: {
        type: 'mditools'
    },
    style: {
        'background': 'transparent',
        'z-index': '9999'
    },
    ui: 'mdi-tools',
    width: 75,
    layout: {
        type: 'hbox',
        align: 'bottom'
    },
    items: [
        {
            xtype: 'button',
            reference: 'leftMenuButton',
            itemId: 'leftMenuButton',
            ui: 'mdi-tools-button-small',
            enableToggle: true,
            iconCls: 'mdi-tools-leftmenu',
            toggleGroup: 'mdiToolsMenu',
            tooltip: '#{사이드 메뉴 펼치기}',
            // mdi tooltipType을 title로 변경 김형민  김형민 부적절한 대체텍스트 제공 pdf#18
            tooltipType : 'title',
            listeners: {
                click: 'onLeftMenuButtonClick'
            }
        },
        {
            xtype: 'button',
            reference: 'topMenuButton',
            itemId: 'topMenuButton',
            ui: 'mdi-tools-button-small',
            enableToggle: true,
            iconCls: 'mdi-tools-topmenu',
            toggleGroup: 'mdiToolsMenu',
            tooltip: '#{사이드 메뉴 접기}',
         // mdi tooltipType을 title로 변경 김형민  김형민 부적절한 대체텍스트 제공 pdf#18 
            tooltipType : 'title',
            listeners: {
                click: 'onTopMenuButtonClick'
            }
        },
        {
            xtype: 'button',
            reference: 'closeAllButton',
            itemId: 'closeAllButton',
            ui: 'mdi-tools-button-small',
            iconCls: 'mdi-tools-closeall',
            tooltip: '#{모든 화면 닫기}',
         // mdi tooltipType을 title로 변경 김형민  김형민 부적절한 대체텍스트 제공 pdf#18 
            tooltipType : 'title',
            listeners: {
                click: 'onCloseAllButtonClick'
            }
        }
    ]
});

/*
 * File: app/view/mdi/TopViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.TopViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mditop'
});

/*
 * File: app/view/mdi/TopViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.TopViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mditop',
    createMenuItems: function(childNodes) {
        var me = this,
            menuItems = [];
        Ext.Array.each(childNodes, function(node) {
        	if(node.get('code').indexOf('SEARCH') != -1) {
        		return;
        	}
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
    },
    onMenuHander: function(item, e) {
        var me = this,
            view = me.getView();
        view.fireEvent('openMenu', item.menuData);
    },
    init: function() {
        var me = this,
            vm = me.getViewModel();
        var menuStore = Mdi.store.Menu;
        var localeStore = Mdi.store.Locale;
        vm.setStores({
            menuStore: menuStore
        });
        if (menuStore.loadCount) {
            me.initMenuBar(menuStore.getRange());
        } else {
            menuStore.on('load', me.onMdiMenuStoreLoad, me, {
                single: true
            });
        }
        if (localeStore.loadCount) {
            me.initLocales(localeStore.getRange());
        } else {
            localeStore.on('load', me.onLocaleStoreLoad, me, {
                single: true
            });
        }
        MdiManager.getDisplayText().then(function(displayText) {
            vm.set('mdiUserName', displayText);
        });
        vm.bind('{currentMenu}', me.onCurrentMenuChange, me);
        Ext.apply(me.getView(), {
            getMenuBar: function() {
                return me.lookupReference('menuBar');
            }
        });
        Etna.onDone(function() {
            if (!vm.get('authenticated') && Mdi.model.Setting.get('authenticatable')) {
            	showPopupList();
                var authenticateZone = me.lookupReference('authenticateZone');
                if(authenticateZone) {
                	authenticateZone.add({
                		xclass: Mdi.model.Setting.get('authenticatorClass')
                	});
                }
            }else{
            	if(!Cmmn.User.get('id')){
            		Cmmn.User.load(function (){
            			showPopupList();
            			showPersonalPopup();
            		});
            	}else{
            		showPopupList();
            		showPersonalPopup();
            	}
            }
        });
    },
    onMdiMenuStoreLoad: function(treeStore, records, successful, operation, node, eOpts) {
        var me = this;
        me.initMenuBar(records);
    },
    onMenuButtonClick: function(button) {
        var me = this,
            view = me.getView();
        if (!view.fireEvent('openMenu', button.menuData)) {
            button.hideMenu();
        }
    },
    onLocaleStoreLoad: function(store, records, successful, eOpts) {
        var me = this;
        me.initLocales(records);
    },
    initMenuBar: function(menus) {
        var me = this,
            vm = me.getViewModel(),
            menuBar = me.lookupReference('menuBar');
        MdiManager.search = {};
        Ext.suspendLayouts();
        menuBar.removeAll();
        var buttons = [];
        Ext.each(menus, function(record) {
            var hiddenFlag = record.get('code').indexOf('SEARCH') != -1 ? true : false;
        	buttons.push(menuBar.add({
                text: record.get('text'),
                menuData: record,
                hidden: hiddenFlag,
                menuId: record.getId(),
                menu: {
                    xtype: 'menu',
                    plain: true,
                    ui: 'mdi-top-menu-sub',
                    shadow : false,
                    ignoreParentClicks: true,
                    items: (me.topMenuMode == 'drop') ? [] : (record.isLeaf() ? null : me.createMenuItems(record.childNodes)),
                    listeners: {
                        deactivate: function(menu) {
                            menu.previousFocus = null;
                        }
                    }
                },
                listeners: {
                    click: (me.topMenuMode == 'drop') ? me.onMenuDropButtonClick : me.onMenuButtonClick,
                    scope: me
                }
            }));
        });
        Ext.resumeLayouts(true);
        if (vm.get('withLeftMenu') && menus.length) {
        	if(menus[0].id.indexOf('SEARCH') !== -1) {
        		me.getView().fireEvent('openMenu', menus[1]);
        		menuBar.getComponent(1).setPressed(true);
        	} else {
        		me.getView().fireEvent('openMenu', menus[0]);
        		menuBar.getComponent(0).setPressed(true);
        	}
        }
    },
    initLocales: function(locales) {
        var me = this;
        MdiManager.getCurrentLoale().then(function(locale) {
            var items = [];
            Ext.each(locales, function(record) {
                items.push({
                    xtype: 'menucheckitem',
                    text: record.get('value'),
                    locale: record.get('key'),
                    group: 'locale',
                    checked: locale == record.get('key'),
                    handler: function(item) {
                        Ext.MessageBox.confirm("#{확인}", '#{언어를 변경 하시려면 페이지를 새로고침 됩니다.\n변경하시겠습니까?}', function(confirm) {
                            if (confirm == "yes") {
                                MdiManager.setCurrentLocale(item.locale).then(function() {
                                    location.reload();
                                }, function() {
                                    Ext.MessageBox.alert("#{오류}", "#{사용자 로케일 변경시 오류가 발생하였습니다.}");
                                });
                            }
                        });
                    }
                });
            });
            me.lookupReference('localeSetting').setMenu(items);
        }, function() {
            Ext.MessageBox.alert("#{오류}", "#{사용자 로케일 조회시 오류가 발생하였습니다.}");
        });
    },
    onCurrentMenuChange: function(menu) {
        var me = this,
            vm = me.getViewModel(),
            menuBar = me.lookupReference('menuBar'),
            menuBreadcrumb = me.lookupReference('menuBreadcrumb'),
            menuStore = vm.getStore('menuStore'),
            rootNode = menuStore.getRoot(),
            button,
            menuName = '| 한국전력 전자조달 시스템'
            ;
        if (!menu || menu.isRoot()) {
            menuBreadcrumb.setSelection(rootNode);
            button = menuBar.down('button[pressed]');
            if (button) {
                button.setPressed(false);
            }
            return;
        }
        menuBreadcrumb.setSelection(menu);
        //2022.03.25 Hoon, 웹접근성 관련 조치, 방대혁 부장님 가이드, 회원가입 첫페이지 강제 설정
        if(menu.data.text == "회원가입"){
        	menu = menu.parentNode;
        	menuName = "회원가입 > 회원선택"; 
        } else {
	        menuName = menu.data.text
	        while (!menu.parentNode.isRoot()) {
	            menu = menu.parentNode;
	            menuName = menu.data.text+' > ' +menuName;
	        }
        }
        menuName = menuName+' | 한국전력 전자조달 시스템';
        
      //김형민 부적절한 페이지 제목제공 pdf#40
        Ext.query('html', parent.document)[0].querySelector('title').innerText = menuName;
        //Ext.query('title')[0].innerHTML = menuName;
        button = menuBar.down(Ext.String.format('button[menuId={0}]', menu.getId()));
        if (button) {
            button.setPressed(true);
        }
        me.onMenuButtonClick(button);
    },
    expandMenuList: function(childNodes, dropMenuIndex) {
        var me = this;
        var returnList = [];
        if (!dropMenuIndex) {
            me.dropMenuIndex = 0;
        } else {
            me.dropMenuIndex = dropMenuIndex;
        }
        Ext.each(childNodes, function(items) {
            items.dropIndex = me.dropMenuIndex;
            returnList.push(items);
            me.dropMenuIndex = me.dropMenuIndex + 1;
            if (items.children) {
                returnList = Ext.Array.merge(returnList, (me.expandMenuList(items.children, me.dropMenuIndex)));
            }
        });
        return returnList;
    },
    onMenuMouseDown: function(e) {
        var me = this,
            menuBar = me.lookupReference('menuBar');
        if ((me.depthMenu && !me.depthMenu.owns(e.target)) && !menuBar.owns(e.target)) {
            me.dropMenuDestroy();
            Ext.un('mousedown', me.onMenuMouseDown, me);
        }
    },
    createDropMenuItems: function(compt, menuItems) {
        var me = this;
        if (me.depthMenu) {
            me.depthMenu.destroy();
        }
        var screenWidth = Ext.getBody().getViewSize().width,
            screenHeight = Ext.getBody().getViewSize().height,
            horizontalCount = 0,
            mergeCount = 0,
            expandMenu = me.expandMenuList(menuItems.data.children);
        
        Ext.each(menuItems.data.children, function(childNode) {
            var childMenuListSize = me.expandMenuList(childNode).length;
            horizontalCount += Math.ceil(childMenuListSize / 14);
            if (childMenuListSize > 14) {
                mergeCount = horizontalCount - 1;
            }
        });
        var paddingCount = (horizontalCount - mergeCount) + 2;
        var currentCenterX = compt.getX() + (compt.getWidth() / 2);
        var menuWidth = horizontalCount * 182;
        var helfMenuWidth = menuWidth / 2;
        var menuPosition = ((screenWidth / 2) > currentCenterX) ? 'L' : 'R';
        var topMenuY = me.getView().getHeight(),
            topMenuX = 0;
        var mmStore = Mdi.store.Menu;
        mmStore.setData(expandMenu);
        me.depthMenu = Ext.create('Mdi.view.mdi.TopDropMenu', {
            id: 'dropMenuContainer',
            store: mmStore,
            listeners: {
                destroy: function() {
                    if (me.lastArrowMenu) {
                        me.lastArrowMenu.removeCls('arrow');
                    }
                },
                mouseleave: {
                    element: 'el',
                    fn: function(e) {
                        if (me.depthMenu) {
                            var isToolTip = false;
                            if (e && e.relatedTarget) {
                                var clsList = e.relatedTarget.classList;
                                if (clsList.contains("x-tip-body") || clsList.contains("x-tip") || clsList.contains("x-box-item") || clsList.contains("x-box-scroller-body-horizontal")) {
                                    isToolTip = true;
                                    e.preventDefault();
                                }
                            }
                            if (me.depthMenu && !isToolTip) {
                                me.dropMenuDestroy();
                            }
                        }
                    }
                },
                mouseover: {
                    element: 'el',
                    fn: function(e, item) {
                        if (item && item.id == 'dropMenuContainer') {
                            if (me.depthMenu) {
                                me.dropMenuDestroy();
                            }
                        }
                    }
                }
            }
        });
        if (menuPosition == 'R') {
            if (screenWidth < menuWidth) {
                me.depthMenu.showAt([
                    compt.getX() + 1,
                    topMenuY
                ]);
            } else {
                if ((screenWidth - currentCenterX) < helfMenuWidth) {
                    me.depthMenu.showAt([
                        currentCenterX - helfMenuWidth - 2,
                        topMenuY
                    ]);
                    topMenuX = (screenWidth - menuWidth) - paddingCount;
                } else {
                    me.depthMenu.show();
                    me.depthMenu.showAt([
                        currentCenterX - helfMenuWidth + 1,
                        topMenuY
                    ]);
                    topMenuX = currentCenterX - helfMenuWidth + 1;
                }
            }
        } else {
            if (currentCenterX < helfMenuWidth) {
                me.depthMenu.showAt([
                    0,
                    topMenuY
                ]);
            } else {
                me.depthMenu.show();
                me.depthMenu.showAt([
                    currentCenterX - helfMenuWidth + 1,
                    topMenuY
                ]);
                topMenuX = currentCenterX - helfMenuWidth + 1;
            }
        }
        me.depthMenu.getEl().dom.style.display = 'none';
        Ext.defer(function() {
            if (me.depthMenu) {
                me.depthMenu.getEl().dom.style.display = '';
                me.depthMenu.setX(topMenuX);
                me.depthMenu.setY(topMenuY);
                me.depthMenu.getEl().dom.style.visibility = 'visible';
            }
        }, 1, me);
        /*me.depthMenu.el.shadow.el.applyStyles({'left':'0px',
                                               'background-color':'#ffffff',
                                               'width':screenWidth+'px',
                                               'top':(me.depthMenu.getY())+'px',
                                               'height':me.depthMenu.getHeight()+'px',
                                               'border-radius':'0px'
                                              });*/
        Ext.on('mousedown', me.onMenuMouseDown, me);
        Ext.on('resize', me.onResizeHandler, me);
    },
    onTopMenuOver: function(mymenu, e) {
        var me = this;
        if (me.depthMenu && me.depthMenu.isFloating()) {
            me.depthMenu.destroy();
        }
        me.createMenuItems(mymenu, record);
    },
    onResizeHandler: function(w, h, e) {
        var me = this;
        if (me.depthMenu) {
            me.depthMenu.destroy();
            Ext.un('resize', me.onResizeHandler, me);
        }
    },
    onMenuDropButtonClick: function(menuCmp) {
        var me = this;
        if (!me.lastArrowMenu) {
            me.dropMenuCreate(menuCmp);
        } else if (menuCmp == me.lastArrowMenu) {
            if (me.depthMenu && !me.depthMenu.isDestroyed) {
                me.dropMenuDestroy();
            } else {
                me.dropMenuCreate(menuCmp);
            }
        } else {
            me.dropMenuDestroy();
            me.dropMenuCreate(menuCmp);
        }
    },
    dropMenuDestroy: function() {
        var me = this;
        if (me.depthMenu) {
            me.depthMenu.destroy();
            delete me.depthMenu;
        }
    },
    dropMenuCreate: function(menuCmp) {
        var me = this;
        me.createDropMenuItems(menuCmp, menuCmp.menuData);
        if (me.lastArrowMenu) {
            me.lastArrowMenu.removeCls('arrow');
        }
        menuCmp.addCls('arrow');
        me.lastArrowMenu = menuCmp;
    },
    onMyAppButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('openApp', me.getView());
    },
    onHomeButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('openHome');
    },
    onBreadcrumbSelectionChange: function(breadcrumb, node, eOpts) {
        var me = this,
            view = me.getView(),
            vm = me.getViewModel(),
            currentMenu = vm.get('currentMenu');
        if (node && !node.isRoot() && (!currentMenu || (node.getId() != currentMenu.getId()))) {
            view.fireEvent('openMenu', node);
        }
    },
    onUserInfoButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('userInfo');
    },
    onAlarmButtonAfterRender: function(component, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('alarmButtonAfterRender', component);
    },
    onMemoButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('openMemo');
    },
    onMdiCatalogButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('openCatalog');
    },
    onMdiShoppingCartButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('openShoppingcart');
    },
    onMdiSettingButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.fireEvent('openSetting');
    },
    onMdiLogoutButtonClick: function(button, e, eOpts) {
        Ext.MessageBox.confirm("#{확인}", '#{로그아웃 하시겠습니까?}', function(confirm) {
            if (confirm == "yes") {
                MdiManager.logout();
            }
        });
    },
    onTopToggleButtonClick: function(button, e, eOpts) {
        var me = this,
            visible = !button.pressed,
            target = [me.lookupReference('top'), me.lookupReference('menuBar')];
        
        button.el.toggleCls('x-btn-toggle-pressed');
        var isCollapsed = button.el.hasCls('x-btn-toggle-pressed');
        button.el.dom.setAttribute('title', isCollapsed ? '상단 메뉴 펼치기' : '상단 메뉴 접기');
        
        Ext.Array.each(target, function(t) {
            t.setVisible(visible);
        });
    },
    onLogoClick : function (){
    	//login 후 화면 이동없이  main으로 이동하도록 요청
    	MdiManager.showSpMain(); 
    },
	onUserNameButtonClick : function(){
    	if(Cmmn.User.get('userType') === 'Internal'){
    		var classPath = 'Spt_Bp_Member.view.myInfoSearch.MyInfo';

    		if (MdiManager.hasView(classPath)) {
    		var view = MdiManager.mdiTab.down(Ext.String.format('>[classpath='+classPath+']'));
    		  MdiManager.mdiTab.remove(view,true);                  
    		}
    		MdiManager.addView(classPath, {  
    		title: '#{나의정보}',
    		authKey:  'MEM10110'
    		 }, classPath); 


    		}else{  // 외부
    		var classPath = 'Spt_Sp_Member.view.myInfoSearch.MyInfoMain';

    		if (MdiManager.hasView(classPath)) {
    		var view = MdiManager.mdiTab.down(Ext.String.format('>[classpath='+classPath+']'));
    		  MdiManager.mdiTab.remove(view,true);                  
    		}
    		MdiManager.addView(classPath, {  
    		title: '#{나의정보}',
    		authKey:  'MEM20110'
    		 }, classPath); 
    		}
    },
    onMdiFindIdPwButtonClick : function (){
    	/*var classpath = 'Cmmn_Sp_Popup.view.member.IDPWSearchMain';
    	var name = '#{ID/비밀번호 찾기}';
        if (MdiManager.hasView(classpath)) {
            MdiManager.showView(classpath);
        } else {
            MdiManager.addView(classpath, {
                title: name,
                authKey: 'MEM30800'
            }, classpath);
        }*/
    	/* 2021.03.16 임상근 ID/PW 찾기 LEFT 메뉴 미생성 수정*/
        var me = this,
	    view = this.getView(),
	    viewportController = view.up('mdiviewport').controller;
	    menu = Mdi.store.Menu.getRoot().findChild('code','MEM30800', true);
        viewportController.onMdiTopOpenMenu(menu); 
    },
    onMdiCertLogInButtonClick : function (){
    	//console.log("onMdiCertLogInButtonClick");
    	/*
		var me = this, CertificationLoginRef = me.lookupReference('CertificationLoginRef2');
		CertificationLoginRef.show();
		CertificationLoginRef.center();
		*/
    	
    	if(isForeign){
    		MdiManager.toggleSpMain(isForeign); 
    	}else{
    		var me = this, KepcoLoginRef = me.lookupReference('KepcoLoginRef');
        	KepcoLoginRef.show();
        	KepcoLoginRef.center();
        	if(document.querySelector('#kepcoLoginPop')) {
        		KepcoLoginRef.setFocusToComponent();
        	}
    	}
    	
    },
    onMemberJoinButtonClick : function (){
    	// 회원가입
    	var classpath = 'Cmmn_Sp_Popup.view.join.MemberJoin';
    	if(isForeign){
    		classpath = 'Cmmn_Sp_Popup.view.join.foreign.MemberJoin';
    	}
    	var name = '#{회원가입}';
        if (MdiManager.hasView(classpath)) {
            MdiManager.showView(classpath);
        } else {
            MdiManager.addView(classpath, {
                title: name,
                authKey: 'MEM30600'
            }, classpath);
        }
    }
});

/*
 * File: app/view/mdi/Top.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.Top', {
    extend: Ext.container.Container,
    alias: 'widget.mditop',
    controller: 'mditop',
    viewModel: {
        type: 'mditop'
    },
    cls: 'mdi-top',
    width: 613,
    
    padding : '0 0 6 0',
    
    layout: 'anchor',
    items: [
        {
            xtype: 'toolbar',
            anchor: '100%',
            reference: 'top',
            height: 30,
            ui: 'mdi-top',
            layout: {
                type: 'hbox',
                align: 'middle'
            },
            items: [
                {
                    xtype: 'button',
                    cls: 'mdi-top-logo',
                    id : 'kepco-mdi-logo-button', //logo 버튼의 아이디를 unique한 아이디로 지정
                    margin : '0 0 0 10',
                    width : 400,
                    height : 18,
                    ui : 'plain',
                    listeners : {
                    	click : 'onLogoClick'
                    }
                },
                {
                    xtype: 'tbspacer',
                    flex : 1
                },
                {
                    xtype : 'button',
                    text : '#{회원가입}',
                    ui: 'mdi-status-quick-button-small',
                    cls : 'mdi-quick-button-lock',
                    iconCls : 'mdi-quick-button-lock-icon',
                    bind : {
                    	hidden : '{authenticated}'
                    },
                    listeners: {
                        click: 'onMemberJoinButtonClick'
                    }
                },
                {
                    xtype: 'component',
                    cls: 'mdi-functionbar-separator',
                    bind : {
                    	hidden : '{authenticated}'
                    }
                },
                {
                    xtype : 'button',
                    text : '#{로그인}',
                    ui: 'mdi-status-quick-button-small',
                    bind : {
                    	hidden : '{authenticated}'
                    },
                    listeners: {
                                click: 'onMdiCertLogInButtonClick'
                    }
                },
                {
                    xtype: 'component',
                    cls: 'mdi-functionbar-separator',
                    bind : {
                    	hidden : '{authenticated}'
                    }
                },
                {
                    xtype: 'button',
                    ui: 'mdi-status-quick-button-small',
                    bind: {
                        hidden: '{!authenticated}',
                        text: '{mdiUserName}'
                    },
                    listeners: {
                        click: 'onUserNameButtonClick'
                    }
                },
                {
                    xtype: 'component',
                    cls: 'mdi-functionbar-separator',
                    bind : {
                    	hidden : '{!authenticated}'
                    }
                },
                {
                    xtype : 'button',
                    text : '#{로그아웃}',
                    ui: 'mdi-status-quick-button-small',
                    bind : {
                    	hidden : '{!authenticated}'
                    },
                    listeners: {
                                click: 'onMdiLogoutButtonClick'
                            }
                },
                {
                    xtype: 'component',
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
        }, {
            xtype: 'toolbar',
            anchor: '100%',
            reference: 'menuBar',
            border: 0,
            cls: 'mdi-top-menu',
            padding: 0,
            ui: 'mdi-top-menubar',
            height : 30,
            defaults: {
                arrowVisible: false,
                ui: 'mdi-top-menu-button-small',
                height: 30,
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
                            tooltip: '#{Home}',
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
                    tooltip: '#{Top Menu Toggle}',
                    listeners: {
                        click: 'onTopToggleButtonClick'
                    }
                }
            ]
        }
    ],
    initConfig: function(instanceConfig) {
        var me = this,
            config = {};
        me.processMdiTop(config);
        if (instanceConfig) {
            me.getConfigurator().merge(me, config, instanceConfig);
        }
        return me.callParent([
            config
        ]);
    },
    processMdiTop: function(config) {}
});

/*
 * File: app/view/mdi/TopDropMenuViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.TopDropMenuViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mditopdropmenu'
});

/*
 * File: app/view/mdi/TopDropMenuViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.TopDropMenuViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mditopdropmenu',
    onDataviewShow: function(component, eOpts) {
        var screenWidth = Ext.getBody().getViewSize().width - component.getX();
        var dropMenus = Ext.get('topMenuDrop').dom.children,
            maxRowCount = 0,
            drawMenuWidth = 1,
            changedIndex = 0;
        Ext.Array.each(dropMenus, function(menuContainer, index) {
            drawMenuWidth += 183;
            maxRowCount = Math.max(maxRowCount, menuContainer.getElementsByTagName('li').length);
            if (maxRowCount > 14) {
                drawMenuWidth += (Math.ceil(maxRowCount / 14) * 182) - 183;
                maxRowCount = 14;
            }
            if (screenWidth < drawMenuWidth) {
                dropMenus[index].className = 'mdi-top-menu-first-container';
                for (var i = index; i >= changedIndex; i--) {
                    var menuContainers = Ext.get(dropMenus[i]).dom.getElementsByClassName('mdi-top-menu-inner-container');
                    if (menuContainers.length > 0) {
                        Ext.Array.each(menuContainers, function(menuContainer) {
                            menuContainer.style.height = (maxRowCount * 25) + 'px';
                        });
                    }
                }
                changedIndex = index;
                drawMenuWidth = 183;
                menuContainer = Ext.get(dropMenus[index]).dom.getElementsByClassName('mdi-top-menu-inner-container')[0];
                maxRowCount = menuContainer.getElementsByTagName('li').length;
                if (maxRowCount > 14) {
                    maxRowCount = 14;
                }
            }
            if ((dropMenus.length - 1) == index) {
                for (var i = index; i >= changedIndex; i--) {
                    var menuContainer = Ext.get(dropMenus[i]).dom.getElementsByClassName('mdi-top-menu-inner-container')[0];
                    if (menuContainer) {
                        menuContainer.style.height = (maxRowCount * 25) + 'px';
                    }
                }
            }
        });
    },
    onDataviewItemClick: function(dataview, record, item, index, e, eOpts) {
        var me = this,
            classpath = record.data.classpath;
        if (record.isLeaf()) {
            if (MdiManager.hasView(classpath)) {
                MdiManager.showView(classpath);
            } else {
                MdiManager.addView(classpath, {
                    title: record.get('text'),
                    authKey: record.get('code')
                }, record.get('requireClass'));
            }
            Ext.defer(function() {
                dataview.destroy();
            }, 1);
        }
    },
    onDataviewAfterRender: function(component, eOpts) {
        var toolTipText = Ext.get('ext-quicktips-tip-innerCt');
        toolTipText.el.applyStyles({
            'color': '#ffffff'
        });
        if (component.getNavigationModel()) {
            component.getNavigationModel().focusCls = 'none';
        }
    }
});

/*
 * File: app/view/mdi/TopDropMenu.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.TopDropMenu', {
    extend: Ext.view.View,
    alias: 'widget.mditopdropmenu',
    controller: 'mditopdropmenu',
    viewModel: {
        type: 'mditopdropmenu'
    },
    reference: 'dropMenuView',
    constrain: true,
    shadow: false,
    floating: true,
    tpl: Ext.create('Ext.XTemplate', '<div id="topMenuDrop">', '    <tpl for=".">', '        <tpl if="depth == 2">', '            <div  class="{[this.isFirstContainer(xindex)]}">', '                <div class="mdi-top-menu-levelmenu2">', '                    <div class="mid-top-menu-item-selector">', '                        <span class="mdi-top-menu-level2-text">{text}</span>', '                    </div>', '                </div>', '                </tpl>', '            <tpl if="depth != 2">', '                <tpl if="this.isMergeStart(values,parent,xindex,xcount,xkey)">', '                    <ul  class="mdi-top-menu-inner-container">', '                        </tpl>', '                    <li class="mdi-top-menu-level" >', '                        <div class="mid-top-menu-item-selector">', '                            <tpl if="!this.isLeaf(values)">', '                                <span class="mdi-surve-menu-text" data-qtip="{text}" data-qclass="mdi-topmenu-tooltip">{text}</span>', '                            </tpl>', '                            <tpl if="this.isLeaf(values)">', '                                <span class="mdi-surve-menu-text {[this.leafCss(values)]}" data-qtip="{text}" data-qclass="mdi-topmenu-tooltip">', '                                    <tpl if="!this.is3Level(values)">', '                                        -', '                                    </tpl>', '                                    {text}', '                                </span>', '                            </tpl>', '                        </div>', '                    </li>', '                    <tpl if="this.isMergeEnd(values,parent,xindex,xcount,xkey)">', '                        </ul>', '                </tpl>', '            </tpl>', '            <tpl if="this.isLastRow(values,parent,xindex,xcount,xkey)">', '                </div>', '        </tpl>', '    </tpl>', '</div>', {
        isLastRow: function(rowData, xparent, xindex, xcount) {
            if (xindex < xcount) {
                if (xparent[xindex].depth == 2) {
                    return true;
                }
            }
            return false;
        },
        isMergeStart: function(rowData, parent, xindex, xcount, xkey) {
            if ((rowData.dropIndex - 1) % 14 == 0) {
                return true;
            }
            return false;
        },
        isMergeEnd: function(rowData, parent, xindex, xcount, xkey) {
            if ((rowData.dropIndex != 1) && ((rowData.dropIndex) % 14) == 0) {
                return true;
            }
            return false;
        },
        leafCss: function(rowData) {
            if (rowData.leaf) {
                var itemOverClass = "mdi-top-menu-item-over";
                return itemOverClass;
            }
            return "";
        },
        isFirstContainer: function(xindex) {
            if (xindex == 1) {
                return "mdi-top-menu-first-container";
            } else {
                return "mdi-top-menu-container";
            }
        },
        isLeaf: function(rowData) {
            return rowData.leaf;
        },
        is3Level: function(rowData) {
            if (rowData.depth == 3) {
                return true;
            }
            return false;
        },
        isMerge: false
    }),
    disableSelection: false,
    itemSelector: '.mid-top-menu-item-selector',
    listeners: {
        show: 'onDataviewShow',
        itemclick: 'onDataviewItemClick',
        afterrender: 'onDataviewAfterRender'
    }
});

/*
 * File: app/view/mdi/UserInfoViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.UserInfoViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mdiuserinfo',
    data: {
        editable: false,
        validPassword: false,
        userData: {}
    },
    validatePassword: function(password) {
        var deferred = Ext.create('Deft.Deferred');
        smartsuit.ui.etnajs.cmmn.MdiController.validatePassword(password, function(result, e) {
            if (e.status) {
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });
        return deferred.promise;
    },
    saveUserInfo: function(userData) {
        var deferred = Ext.create('Deft.Deferred');
        saveData = {
            password: userData.password,
            username: userData.username,
            name: userData.name,
            englishName: userData.englishName,
            email: userData.email,
            phoneNo: userData.phoneNo,
            mobileNo: userData.mobileNo,
            faxNo: userData.faxNo
        };
        smartsuit.ui.etnajs.cmmn.MdiController.saveUserInfo(saveData, function(result, e) {
            if (e.status) {
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });
        return deferred.promise;
    }
});

/*
 * File: app/view/mdi/UserInfoViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.UserInfoViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mdiuserinfo',
    isValid: function() {
        var me = this;
        var userInfoForm = me.lookupReference('UserInfoForm').getForm();
        var message = '';
        if (!userInfoForm.isValid()) {
            var fields = userInfoForm.getFields().items;
            Ext.each(fields, function(field) {
                if (!field.isValid()) {
                    if (field.itemId === 'email') {
                        Etna.Message.alert('#{이메일 형식에 맞게 입력하세요.}');
                        validationYn = false;
                        return false;
                    }
                    message = Ext.String.format('#{{0} 을(를) 입력하세요.}', field.fieldLabel);
                    Etna.Message.alert(message);
                    validationYn = false;
                    return false;
                }
            });
        } else {
            return true;
        }
    },
    getUserData: function() {
        var userData = Ext.clone(Cmmn.User.getData());
        userData.passwordCheck = userData.password;
        return userData;
    },
    validatePassword: function() {
        var me = this,
            vm = me.getViewModel();
        var userData = vm.get('userData');
        vm.set('validPassword', false);
        if (userData.password != userData.passwordCheck) {
            Etna.Message.alert('#{비밀번호 확인을 해야합니다.}');
            vm.set('validPassword', false);
        } else {
            if (Cmmn.User.getData().password === userData.passwordCheck) {
                vm.set('validPassword', true);
            } else {
                var returnData = false;
                var password = userData.password;
                vm.validatePassword(password).then({
                    success: function(result) {
                        if (result.resultMessageCode === 'pw.result.success') {
                            vm.set('validPassword', true);
                        } else {
                            Etna.Message.alert(result.resultMessage);
                            vm.set('validPassword', false);
                        }
                    }
                }).always(function() {}).done();
            }
        }
    },
    onEditButtonClick: function(button, e, eOpts) {
        var me = this,
            vm = me.getViewModel();
        vm.set('editable', true);
    },
    onEditCancelButtonClick: function(button, e, eOpts) {
        var me = this,
            vm = me.getViewModel();
        vm.set('userData', {});
        Etna.onDone(function() {
            vm.set('userData', me.getUserData());
            vm.set('editable', false);
        });
    },
    onSaveButtonClick: function(button, e, eOpts) {
        var me = this,
            vm = me.getViewModel(),
            view = me.getView();
        var userData = vm.get('userData');
        if (me.isValid()) {
            me.validatePassword();
            Etna.onDone(function() {
                var validPassword = vm.get('validPassword');
                if (validPassword) {
                    view.setLoading(true);
                    vm.saveUserInfo(userData).then({
                        success: function() {
                            Etna.Message.alert('#{저장 하였습니다.}');
                        }
                    }).always(function() {
                        Cmmn.User.doLoad(function(result) {
                            this.setData(result);
                            this.setLastModified(Date.now());
                        });
                        view.setLoading(false);
                    }).done();
                }
            });
        }
    },
    onCloseButtonClick: function(button, e, eOpts) {
        var me = this,
            view = me.getView();
        view.close();
    },
    onPanelAfterRender: function(component, eOpts) {
        var me = this,
            vm = me.getViewModel(),
            view = me.getView();
        view.setLoading(true);
        Etna.onDone(function() {
            var userData = me.getUserData();
            vm.set('userData', userData);
            view.setLoading(false);
        });
    }
});

/*
 * File: app/view/mdi/UserInfo.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.UserInfo', {
    extend: Ext.panel.Panel,
    alias: 'widget.mdiuserinfo',
    controller: 'mdiuserinfo',
    viewModel: {
        type: 'mdiuserinfo'
    },
    height: 350,
    ui: 'popup',
    width: 600,
    bodyBorder: true,
    title: '#{사용자 정보}',
    layout: {
        type: 'vbox',
        align: 'stretch'
    },
    dockedItems: [
        {
            xtype: 'toolbar',
            dock: 'top',
            items: [
                {
                    xtype: 'tbfill'
                },
                {
                    xtype: 'button',
                    text: '#{수정}',
                    bind: {
                        hidden: '{editable}'
                    },
                    listeners: {
                        click: 'onEditButtonClick'
                    }
                },
                {
                    xtype: 'button',
                    text: '#{수정취소}',
                    bind: {
                        hidden: '{!editable}'
                    },
                    listeners: {
                        click: 'onEditCancelButtonClick'
                    }
                },
                {
                    xtype: 'button',
                    text: '#{저장}',
                    bind: {
                        hidden: '{!editable}'
                    },
                    listeners: {
                        click: 'onSaveButtonClick'
                    }
                },
                {
                    xtype: 'button',
                    text: '#{닫기}',
                    listeners: {
                        click: 'onCloseButtonClick'
                    }
                }
            ]
        }
    ],
    listeners: {
        afterrender: 'onPanelAfterRender'
    },
    initConfig: function(instanceConfig) {
        var me = this,
            config = {
                items: [
                    me.processUserInfoForm({
                        xtype: 'form',
                        flex: 1,
                        reference: 'UserInfoForm',
                        bodyPadding: 10,
                        layout: {
                            type: 'table',
                            columns: 2,
                            tableAttrs: {
                                style: {
                                    width: '100%'
                                }
                            },
                            tdAttrs: {
                                style: {
                                    width: '100%',
                                    paddingRight: '10px'
                                }
                            }
                        },
                        items: [
                            {
                                xtype: 'textfield',
                                colspan: 2,
                                reference: 'userName',
                                width: 250,
                                fieldLabel: '#{사용자 ID}',
                                readOnly: true,
                                allowBlank: false,
                                enforceMaxLength: true,
                                maxLength: 36,
                                bind: {
                                    value: '{userData.username}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                reference: 'name',
                                width: 250,
                                fieldLabel: '#{이름}',
                                allowBlank: false,
                                enforceMaxLength: true,
                                maxLength: 50,
                                bind: {
                                    value: '{userData.name}',
                                    readOnly: '{!editable}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                reference: 'englishName',
                                width: '100%',
                                fieldLabel: '#{이름(영문)}',
                                enforceMaxLength: true,
                                maxLength: 50,
                                bind: {
                                    value: '{userData.englishName}',
                                    readOnly: '{!editable}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                reference: 'password',
                                width: 250,
                                fieldLabel: '#{비밀번호}',
                                inputType: 'password',
                                allowBlank: false,
                                maxLength: 100,
                                bind: {
                                    value: '{userData.password}',
                                    readOnly: '{!editable}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                reference: 'passwordCheck',
                                width: 250,
                                fieldLabel: '#{비밀번호 확인}',
                                inputType: 'password',
                                allowBlank: false,
                                maxLength: 100,
                                bind: {
                                    value: '{userData.passwordCheck}',
                                    readOnly: '{!editable}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                reference: 'companyName',
                                width: 250,
                                fieldLabel: '#{회사}',
                                readOnly: true,
                                emptyText: '없음',
                                bind: {
                                    value: '{userData.companyName}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                reference: 'departmentName',
                                width: 250,
                                fieldLabel: '#{부서}',
                                readOnly: true,
                                maxLength: 36,
                                bind: {
                                    value: '{userData.departmentName}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                colspan: 2,
                                reference: 'email',
                                itemId: 'email',
                                width: '100%',
                                fieldLabel: '#{이메일}',
                                enforceMaxLength: true,
                                maxLength: 50,
                                vtype: 'email',
                                bind: {
                                    value: '{userData.email}',
                                    readOnly: '{!editable}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                reference: 'phoneNo',
                                width: 250,
                                fieldLabel: '#{전화번호}',
                                enforceMaxLength: true,
                                maxLength: 18,
                                bind: {
                                    value: '{userData.phoneNo}',
                                    readOnly: '{!editable}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                reference: 'mobileNo',
                                width: 250,
                                fieldLabel: '#{H.P 번호}',
                                enforceMaxLength: true,
                                maxLength: 18,
                                bind: {
                                    value: '{userData.mobileNo}',
                                    readOnly: '{!editable}'
                                }
                            },
                            {
                                xtype: 'textfield',
                                reference: 'faxNo',
                                width: 250,
                                fieldLabel: '#{Fax 번호}',
                                enforceMaxLength: true,
                                maxLength: 18,
                                bind: {
                                    value: '{userData.faxNo}',
                                    readOnly: '{!editable}'
                                }
                            }
                        ]
                    })
                ]
            };
        if (instanceConfig) {
            me.getConfigurator().merge(me, config, instanceConfig);
        }
        return me.callParent([
            config
        ]);
    },
    processUserInfoForm: function(config) {
        return config;
    }
});

/*
 * File: app/view/mdi/ViewportViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.ViewportViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mdiviewport',
    data: {
        withLeftMenu: true,
        currentMenu: null,
        authenticated: false,
        catalogHidden: false,
        shoppingCartHidden: false
    },
    formulas: {
        isShoppingCartHidden: {
            get: function(data) {
                return !(this.get('authenticated') && !this.get('shoppingCartHidden'));
            },
            bind: '{authenticated}'
        },
        isCatalogHidden: {
            get: function(data) {
                return !(this.get('authenticated') && !this.get('catalogHidden'));
            },
            bind: '{authenticated}'
        }
    },

    setKeepSession: function() {
        var deferred = Ext.create('Deft.Deferred');

        smartsuit.ui.etnajs.cmmn.MdiController.keepSession(function(result,e){
            if(e.status){
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });

        return deferred.promise;
    }, 
    
    updateUserInfoDestroy: function(agreeYn) {
        var deferred = Ext.create('Deft.Deferred');
        
        smartsuit.ui.etnajs.spt.member.MemberInfoController.userDestoryInfo(agreeYn, function(result,e){
            if(e.status){
                deferred.resolve(result);
            } else {
                deferred.reject(e);
            }
        });

        return deferred.promise;
    }
    
});

/*
 * File: app/view/mdi/popup/ChangePasswordPopupViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.popup.ChangePasswordPopupViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mdipopupchangepasswordpopup',
    data: {
        pwParam: {
            newPassword: null,
            newPasswordCheck: null,
            registrationNo: null
        }
    }
});

/*
 * File: app/view/mdi/popup/ChangePasswordPopupViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.popup.ChangePasswordPopupViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mdipopupchangepasswordpopup',
    init: function() {
        var me = this,
            view = me.getView(),
            vm = me.getViewModel();
    },
    updateCredentialNonExpired: function(isUpdate) {
        var me = this;
        if (isUpdate === false) {
            // credentialNonExpired = true
            smartsuit.ui.etnajs.cmmn.CommonController.setCredentialNonExpired(function(record, option, success) {
                me.getView().close();
            });
        } else {
            me.getView().close();
        }
    },
    onChangeButtonClick: function(button, e, eOpts) {
    	var me = this;
        pageMove('myInfo');
        me.getView().close();
    },
    onCloseButtonClick: function(button, e, eOpts) {
        var me = this,
            forceParam = me.getView().forceParam;
        if (forceParam.isPasswordCycle === true) {
            // 패스워드 변경주기 만료
            me.updateCredentialNonExpired(forceParam.isForceChangePasswordCycle);
        } else if (forceParam.isPasswordCycle === false) {
            // 임시 패스워드 발급
            me.updateCredentialNonExpired(forceParam.isForceChangeNewPassword);
        } else {
            me.getView().close();
        }
    }
});

/*
 * File: app/view/mdi/popup/ChangePasswordPopup.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.popup.ChangePasswordPopup', {
    extend: Ext.window.Window,
    alias: 'widget.mdipopupchangepasswordpopup',
    controller: 'mdipopupchangepasswordpopup',
    viewModel: {
        type: 'mdipopupchangepasswordpopup'
    },
    width:  400,
    title: '#{비밀번호 변경}',
    modal: true,
    layout: {
        type: 'vbox',
        align: 'stretch'
    },
    items: [
    	{
    		xtype: 'displayfield',
    		height: 50,
    		margin: 5,
            value: '#{한국전력공사 전자조달시스템은 개인정보 보호정책에 따라<br>3개월 주기로 비밀번호 변경을 안내 해 드리고 있습니다.}'
    	},
    	{
    		xtype: 'toolbar',
    		dock: 'bootom',
            cls: 'func-toolbar',
            items: [
            	
            	{
                    xtype: 'tbspacer',
                    flex: 1
                },
                {
                    xtype: 'button',
                    iconCls: 'btn-refresh',
                    text: '#{변경}',
                    listeners: {
                        click: 'onChangeButtonClick'
                    }
                },
                {
                    xtype: 'button',
                    iconCls: 'btn-close',
                    text: '#{닫기}',
                    listeners: {
                        click: 'onCloseButtonClick'
                    }
                }
            ]
    	}
    	
    ]
});

/*
 * File: app/view/mdi/popup/LatestAccessUserInfoViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.popup.LatestAccessUserInfoViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mdipopuplatestaccessuserinfo'
});

/*
 * File: app/view/mdi/popup/LatestAccessUserInfoViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.popup.LatestAccessUserInfoViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mdipopuplatestaccessuserinfo',
    onWindowAfterRender: function(component, eOpts) {
        var me = this,
            view = me.getView(),
            userInfo = view.userInfo;
        if (view && userInfo) {
            view.lookupReference('userId').setValue(userInfo.userId);
            view.lookupReference('lastRequest').setValue(userInfo.lastRequest);
            view.lookupReference('latestRequestIp').setValue(userInfo.latestRequestIp);
        }
    }
});

/*
 * File: app/view/mdi/popup/LatestAccessUserInfo.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.popup.LatestAccessUserInfo', {
    extend: Ext.window.Window,
    alias: 'widget.mdipopuplatestaccessuserinfo',
    controller: 'mdipopuplatestaccessuserinfo',
    viewModel: {
        type: 'mdipopuplatestaccessuserinfo'
    },
    width: 340,
    referenceHolder: true,
    title: '#{최근 접속 정보}',
    modal: true,
    layout: {
        type: 'vbox',
        align: 'stretch'
    },
    items: [
        {
            xtype: 'form',
            cls: 'data-form',
            margin: '0 5 5 5',
            bodyBorder: true,
            bodyPadding: 10,
            layout: {
                type: 'vbox',
                align: 'stretch'
            },
            items: [
                {
                    xtype: 'fieldcontainer',
                    fieldLabel: '#{사용자 아이디}',
                    labelWidth: 130,
                    layout: {
                        type: 'table',
                        columns: 1
                    },
                    items: [
                        {
                            xtype: 'textfield',
                            reference: 'userId',
                            readOnly: true
                        }
                    ]
                },
                {
                    xtype: 'fieldcontainer',
                    fieldLabel: '#{최근 접속 일시}',
                    labelWidth: 130,
                    layout: {
                        type: 'table',
                        columns: 1
                    },
                    items: [
                        {
                            xtype: 'textfield',
                            reference: 'lastRequest',
                            readOnly: true
                        }
                    ]
                },
                {
                    xtype: 'fieldcontainer',
                    fieldLabel: '#{최근 접속 아이피}',
                    labelWidth: 130,
                    layout: {
                        type: 'table',
                        columns: 1
                    },
                    items: [
                        {
                            xtype: 'textfield',
                            reference: 'latestRequestIp',
                            readOnly: true
                        }
                    ]
                }
            ]
        }
    ],
    listeners: {
        afterrender: 'onWindowAfterRender'
    }
});

/*
 * File: app/view/mdi/ViewportViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.ViewportViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mdiviewport',
    config: {
        defaultViewConfig: {
            closable: true,
            floating: false,
            border: false,
            frame: false,
            resizable: false,
            cls: 'mdi-module'
        }
    },
    createHomeView: function() {
        var me = this,
            tabpanel = me.lookupReference('mdiTabPanel');
        return Ext.applyIf({
            closable: false,
            header: false,
            title: 'home'
        }, tabpanel.defaults);
    },
    init: function() {
        var me = this,
            vm = me.getViewModel(),
            tabpanel = me.lookupReference('mdiTabPanel');
            
        tabpanel.on('beforetogglespmain', function() {
    		var vm = me.getViewModel();
    		return vm.get('authenticated');
    	});
        
        //2016.03.28 hc.ko
        //내부 사용자인 경우 로그인 후 29분에 한번씩 서버의 temp Controller를 호출하여 Session을 유지 시킴
        try{
	        var chkCount = 0;        
	        if(!Cmmn.User.get('id')){
	    		Cmmn.User.load(function (){
	    			
	    			// 개인정보 보호 절차 개선에 따른 수정사항
	    			// 메일이 발송되었는데 아직 결과를 수신받지 못한 사용자 개인정보 보호 동의 팝업 호출
	    			if( Cmmn.User.data ){
		    			if( Cmmn.User.data.destroyEmailSendYn === true && Cmmn.User.data.destroyInfoReceiveYn === false){
		    				if( Ext.Date.format(new Date(Cmmn.User.data.destroyDisableDueDate), 'Ymd') > Ext.Date.format(new Date(), 'Ymd')){
		    					Etna.Message.confirm('#{개인정보 연장 동의 하시겠습니까? <br> <p style="color:red">미동의시 시스템 이용이 중지 됩니다.</p>}', function(confirm) {
		    						var agreeYn = "";
			    					if(confirm === 'yes') {
			    						agreeYn = "Y";
		    				        }else if(confirm === 'no') {
		    				        	agreeYn = "N";
		    				        }
			    					if( agreeYn === "Y" || agreeYn === "N"){
			    						vm.updateUserInfoDestroy(agreeYn).then({
				    	    			    success: function () {
				    	    			        Etna.Message.alert('#{처리되었습니다.}');
				    	    			        if( agreeYn === "N"){
				    	    			        	MdiManager.logout();
				    	    			        }
				    	    			    },
				    	    			    failure: function () {
				    	    			    	
				    	    			    }
				    	    			}).done();
			    					}
			    					
			    					
			    				});
		    				}
		    			}
	
		    			if(Cmmn.User.data.userType === 'Internal'){
		    				var sessionTimer = Ext.interval(function() {
					             if(chkCount<20){
					            	 vm.setKeepSession();
					            	 chkCount++;
					             }else{
					                 clearInterval(vm.get('sessionTimer'));
					                 vm.set('sessionTimer', '');
					             }
					         }, 1740000);
		    				vm.set('sessionTimer', sessionTimer);
		    			}
	    			}
	    		});
	    	}
        }catch(e){}
        
        MdiManager.isAuthenticated().then(function(authenticated) {
        	var createHome = function() {
            	Ext.env.Ready.on(function() {
            		var homeConfig = me.createHomeView();
            		Ext.apply(homeConfig, {
            			stateful: authenticated
            		});
            		Ext.defer(function(){
            			Mdi.controller.Manager.addViewToTab('Portal.view.Portal', homeConfig);
            		}, 500);
            		
            	});
            };
            vm.set('authenticated', authenticated);
            if (authenticated) {
                me.popupProcess();
            }
            if (authenticated) {
            	if(tabpanel.stateful) {
	                delete tabpanel.statefulLock;
	                var state = Ext.state.Manager.get(tabpanel.stateId);
	                if (state && state.items) {
	                    var applyState = function() {
	                            tabpanel.applyState(state);
	                            tabpanel.statefulLock = true;
	                        };
	                        
	                        
                        applyState();
                        /*
	                    if (Mdi.store.UnauthorizedMenu.isLoaded()) {
	                    } else {
	                        Mdi.store.UnauthorizedMenu.on('load', applyState, me, {
	                            order: 'after',
	                            single: true
	                        });
	                    }
	                    */
	                } else {
	                    createHome();
	                }
            	}
            	else {
            		createHome();
            	}
            } 
            /*
            Portal 로그인하지 않은경우 포탈사용안함 
            else {
                createHome();
            }
            */
        }, function() {
            Ext.Msg.alert('#{오류}', '#{인증 여부 조회시 오류 발생하였습니다.}');
        });
        /*
        Mdi.store.UnauthorizedMenu.load({
            params: {
                kind: Mdi.model.Setting.get('kind')
            }
        });
        */
        Mdi.store.Menu.load({
            params: {
                kind: Mdi.model.Setting.get('kind')
            }
        });
        Mdi.controller.Manager.init(tabpanel);
    },
    isStartupOpenMenuEnabled: function() {
        var me = this,
            vm = me.getViewModel();
        return vm.get('withLeftMenu');
    },
    sendMenuCode: function(menuCode) {
        try {
            smartsuit.ui.etnajs.cmmn.CommonController.saveCurrentMenuCode(menuCode, function() {});
        } catch (e) {}
    },
    onChangePassword: function() {
        var me = this,
            error = false;
        try {
            smartsuit.ui.etnajs.cmmn.CommonController.preloadChangePassword(function(record, option, success) {
                var isChangePassPopup = false;
                var isRegistrationNoNull = false;
                if (success && record.passwordCycleChangeExpired === true) {
                    // 패스워드 변경주기 만료
                    isChangePassPopup = true;
                    record['isPasswordCycle'] = true;
                    record['title'] = "";
                } else if (success && record.credentialsNonExpired === false) {
                    // 임시 패스워드 발급 후 새 패스워드 등록 ( forceChangePassword )
                    isChangePassPopup = true;
                    record['isPasswordCycle'] = false;
                    record['title'] = "#{새 비밀번호 등록}";
                } 
                
                if (success && record.registrationNoNull === true){
                	isRegistrationNoNull = true;
                }
                
                //'17.7.6 김석수. 자재처 권은진 차장 요청사항 반영
                if (!record.latestLoginYn && (Cmmn.User.get('userType') === 'External')) {
                	Etna.Message.confirm('장기간 미접속 하셨습니다.<br>회원정보를 최신 정보로 수정하시겠습니까?', function(msg) {
                		if(msg === 'yes') {
                			pageMove('myInfo');
                		}
                	});
                }
                
                //'17.7.6 김석수. 자재처 권은진 차장 요청사항 반영
                if (!record.mobileNoYn && (Cmmn.User.get('userType') === 'External')) {
                	Etna.Message.confirm('회원정보에 휴대폰 정보가 없습니다.<br>회원정보를 수정하시겠습니까?', function(msg) {
                		if(msg === 'yes') {
                			pageMove('myInfo');
                		}
                	});
                }
                
                if (isChangePassPopup || isRegistrationNoNull) {
                    Ext.require('Mdi.view.mdi.popup.ChangePasswordPopup', function() {
                        var window = Ext.create('Mdi.view.mdi.popup.ChangePasswordPopup', {
                            	isChangePassPopup: isChangePassPopup,
                            	isRegistrationNoNull: isRegistrationNoNull,
                                title: record['title'],
                                forceParam: {
                                    isPasswordCycle: record['isPasswordCycle'],
                                    isForceChangeNewPassword: record['forceChangeNewPassword'],
                                    isForceChangePasswordCycle: record['forceChangePasswordCycle']
                                }
                            });
                        window.show();
                    });
                } else {
                    me.onLatestAccessUserInfo();
                }
            });
        } catch (e) {}
    },
    setCurrentMenu: function(code) {
        var me = this,
            vm = me.getViewModel();
        if(code && code.indexOf('SEARCH') != -1 && MdiManager.search.currentMenu) {
            code = MdiManager.search.currentMenu.get('code');
        }
        Etna.security.Manager.setAuthKey(code);
        vm.set('currentMenu', Mdi.store.Menu.getRoot().findChild('code', code, true));
        me.sendMenuCode(code);
    },
    popupProcess: function() {
        var me = this;
        me.onChangePassword();
    },
    onLatestAccessUserInfo: function() {
        var me = this,
            error = false;
        try {
            smartsuit.ui.etnajs.cmmn.CommonController.getLatestAccessUserInfo(function(record, option, success) {
                if (success) {
                    if (record) {
                        Ext.require('Mdi.view.mdi.popup.LatestAccessUserInfo', function() {
                            var window = Ext.create('Mdi.view.mdi.popup.LatestAccessUserInfo', {
                                    userInfo: {
                                        userId: record['userId'],
                                        latestRequestIp: record['latestRequestIp'],
                                        lastRequest: record['lastRequestStr']
                                    }
                                });
                            window.show();
                        });
                    }
                }
            });
        } catch (e) {}
    },
    onMdiTopOpenMenu: function(menu, eventOptions) {
        var me = this,
            vm = me.getViewModel(),
            classpath = menu.get('classpath'),
            mdiLeft = me.lookupReference('mdiLeft');
        var addOrShow = function() {
                if (MdiManager.hasView(classpath)) {
                    MdiManager.showView(classpath);
                } else {
                    MdiManager.addView(classpath, {
                        title: menu.get('text'),
                        authKey: menu.get('code')
                    }, menu.get('requireClass'));
                }
            };
        if (vm.get('withLeftMenu')) {
            if (menu.isLeaf()) {
                addOrShow();
            } else {
                mdiLeft.setMenu(menu);
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
    },
    onMdiTopOpenHome: function(eventOptions) {
        Mdi.controller.Manager.showView('Portal.view.Portal');
    },
    onMdiTopOpenApp: function(mdiTop, eventOptions) {
        var me = this,
            view = me.getView(),
            viewSize = view.getSize();
        if (!me.mdiMyApp) {
            me.mdiMyApp = Ext.create('Mdi.view.mdi.MyApp', {
                width: viewSize.width - 60,
                height: viewSize.height - 100
            });
            me.mon(view, 'resize', function() {
                viewSize = this.getSize();
                var width = viewSize.width - 60,
                    height = viewSize.height - 100;
                if (width != me.mdiMyApp.getWidth()) {
                    me.mdiMyApp.setWidth(width);
                }
                if (height != me.mdiMyApp.getHeight()) {
                    me.mdiMyApp.setHeight(height);
                }
            });
        }
        me.mdiMyApp.showBy(mdiTop, 'bl', [
            30,
            10
        ]);
    },
    onMdiTopI18nEdit: function(eventOptions) {
        var me = this;
        var tabpanel = me.lookupReference("mdiTabPanel");
        var activeTab = tabpanel.getActiveTab();
        var editor = me.lookupReference('i18nEditor');
        editor.show();
        editor.load(activeTab.classpath);
    },
    onOpenMemo: function(eventOptions) {
        //var me = this;
        //if(!me.note){
        //    me.note = Ext.create('CmmnAdmin.view.memo.MemoWindow');
        //}
        //me.note.show();
        var me = this;
        if (!me.once) {
            //Ext.require("CmmnAdmin.view.memo.MemoSticker", function(){
            CmmnAdmin.view.memo.MemoSticker.loadSticker();
            //});
            me.once = true;
        }
    },
    onAlarmButtonAfterRender: function(component, eventOptions) {
        try {
            var menu = Ext.create('CmmnAdmin.view.calendar.form.AlarmMenu', {
                    listeners: {
                        'noticeAdd': {
                            fn: function() {
                                component.showMenu();
                            }
                        }
                    }
                });
            component.setMenu(menu);
        } catch (e) {
            component.setDisabled(true);
        }
    },
    onOpenCatalog: function(eventOptions) {
        var me = this;
        MdiManager.addView('PublicPro.view.catalog.CatalogProductList', {
            title: '#{카탈로그 구매}'
        });
    },
    onOpenShoppingcart: function(eventOptions) {
        var me = this,
            popup = Ext.create('PublicPro.view.catalog.CatalogProductDetailPopup', {
                modal: true,
                title: '#{장바구니}',
                activeItem: 1,
                layout: {
                    type: 'card',
                    activeItem: 1
                }
            });
        popup.show();
        popup.loadCartList();
    },
    onOpenUserInfo: function(eventOptions) {
        var me = this;
        var tabpanel = me.lookupReference("mdiTabPanel");
        var activeTab = tabpanel.getActiveTab();
        var profile = me.lookupReference('userInfo');
        profile.show();
    },
    onOpenSetting: function(eventOptions) {
        var me = this,
            settingWindow = Ext.create('Ext.window.Window', {
                modal: true,
                height: 200,
                floating: true,
                closable: true,
                closeAction: 'hide',
                title: '#{환경설정}',
                items: [
                    {
                        xclass: 'Account.view.account.Setting',
                        header: false,
                        border: false
                    }
                ]
            });
        settingWindow.show();
    },
    onMdiTabPanelTabChange: function(tabPanel, newCard, oldCard, eOpts) {
        var me = this;
        if (newCard) {
            me.setCurrentMenu(newCard.authKey);
        }
    },
    onTabpanelRender: function(component, eOpts) {
        if (component.useProgressBarMask) {
            Ext.apply(component, {
                loadMask: Ext.create('Ext.LoadMask', {
                    target: component,
                    hidden: true,
                    msgCls: 'progressbar',
                    cls: 'x-mask-msg mdi-tab-progressbar',
                    renderTpl: [
                        '<div id="{id}-msgEl" data-ref="msgEl" role="{role}"',
                        '<tpl if="ariaAttr"> {ariaAttr}</tpl>',
                        ' class="{[values.$comp.msgCls]} ',
                        Ext.baseCSSPrefix,
                        'mask-msg-inner {childElCls}">',
                        '<span></span>',
                        '</div>',
                        '<div id="{id}-msgTextEl" data-ref="msgTextEl" class="',
                        Ext.baseCSSPrefix,
                        'mask-msg-text',
                        '{childElCls}">{msg}</div>'
                    ],
                    listeners: {
                        beforehide: function() {
                            var me = this;
                            if (me.el.getStyle('opacity') == 1) {
                                me.animate({
                                    to: {
                                        opacity: 0
                                    },
                                    listeners: {
                                        afteranimate: function() {
                                            me.hide();
                                            me.setStyle('opacity', 1);
                                        }
                                    }
                                });
                                return false;
                            }
                        }
                    }
                })
            });
        }
    },
    onTabbarAfterRender: function(component, eOpts) {
        var me = this,
            view = me.getView(),
            el = component.getEl();
        var toolsContainer = Ext.dom.Helper.insertBefore(el.last(), {
                tag: 'div',
                cls: 'mdi-tools-container'
            }, true);
        var tools = me.lookupReference('tools');
        view.remove(tools, false);
        tools.floating = false;
        tools.render(toolsContainer);
        tools.setHeight('100%');
        tools.show();
    },
    onMdiTabClick: function(tab, e) {
        if (e.ctrlKey && tab.isTab && tab.card.classpath && tab.card.closable) {
            MdiManager.refreshView(tab.card.classpath);
        }
    },
    onMdiLeftOpenMenu: function(menu, eventOptions) {
        var me = this,
            vm = me.getViewModel(),
            classpath = menu.get('classpath');
        var addOrShow = function() {
                if (MdiManager.hasView(classpath)) {
                    MdiManager.showView(classpath);
                } else {
                    MdiManager.addView(classpath, {
                        title: menu.get('text'),
                        authKey: menu.get('code')
                    }, menu.get('requireClass'));
                }
            };
        if (menu.isLeaf()) {
            addOrShow();
        }
    },
    onMdiLeftExpand: function(p, eOpts) {
        var me = this,
            vm = me.getViewModel(),
            menuBar = me.lookupReference('mdiTop').getMenuBar();
        vm.set('withLeftMenu', true);
        if (menuBar.lastFocusedChild) {
            p.setMenu(menuBar.lastFocusedChild.menuData);
        }
    },
    onTreepanelCollapse: function(p, eOpts) {
        var me = this,
            vm = me.getViewModel();
        vm.set('withLeftMenu', false);
    },
    onToolsTopMenu: function(eventOptions) {
        var me = this,
            vm = me.getViewModel();
        var left = me.lookupReference('mdiLeft');
        left.collapse(Ext.Component.DIRECTION_LEFT);
    },
    onToolsLeftMenu: function(eventOptions) {
        var me = this,
            vm = me.getViewModel();
        var left = me.lookupReference('mdiLeft');
        left.expand();
    },
    onToolsCloseAll: function(eventOptions) {
        MdiManager.closeAll();
    }
});

/*
 * File: app/view/mdi/Viewport.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
/*
    작성자:고재훈
*/
Ext.define('Mdi.view.mdi.Viewport', {
    extend: Ext.container.Viewport,
    alias: 'widget.mdiviewport',
    controller: 'mdiviewport',
    viewModel: {
        type: 'mdiviewport'
    },
    requires : ['Mdi.store.UnauthorizedMenu'],
    layout: 'border',
    defaultListenerScope: true,
    initConfig: function(instanceConfig) {
        var me = this,
            config = {
                items: [
                    {
                        xtype: 'mditop',
                        reference: 'mdiTop',
                        itemId: 'mdiTop',
                        region: 'north',
                        listeners: {
                            openMenu: {
                                fn: 'onMdiTopOpenMenu',
                                scope: 'controller'
                            },
                            openHome: {
                                fn: 'onMdiTopOpenHome',
                                scope: 'controller'
                            },
                            openApp: {
                                fn: 'onMdiTopOpenApp',
                                scope: 'controller'
                            },
                            i18nEdit: {
                                fn: 'onMdiTopI18nEdit',
                                scope: 'controller'
                            },
                            openMemo: {
                                fn: 'onOpenMemo',
                                scope: 'controller'
                            },
                            alarmButtonAfterRender: {
                                fn: 'onAlarmButtonAfterRender',
                                scope: 'controller'
                            },
                            openCatalog: {
                                fn: 'onOpenCatalog',
                                scope: 'controller'
                            },
                            openShoppingcart: {
                                fn: 'onOpenShoppingcart',
                                scope: 'controller'
                            },
                            userInfo: {
                                fn: 'onOpenUserInfo',
                                scope: 'controller'
                            },
                            openSetting: {
                                fn: 'onOpenSetting',
                                scope: 'controller'
                            }
                        }
                    },
                    /*
                     * 2021.01.27 임상근 Tab 포커싱 순서 변경을 위해 생성 순서 변경 
                     */
                    me.processMdiLeft({
                        xtype: 'mdileft',
                        reference: 'mdiLeft',
                        collapseMode: 'mini',
                        region: 'west',
                        listeners: {
                            openMenu: {
                                fn: 'onMdiLeftOpenMenu',
                                scope: 'controller'
                            },
                            expand: {
                                fn: 'onMdiLeftExpand',
                                scope: 'controller'
                            },
                            collapse: {
                                fn: 'onTreepanelCollapse',
                                scope: 'controller'
                            }
                        }
                    }),
                    me.processMdiTabPanel({
                        xtype: 'tabpanel',
                        getState: function() {
                            var me = this,
                                state = {},
                                items = [];
                            Ext.Array.each(me.items.getRange(), function(item) {
                                var cfg = {
                                        classpath: item.$className,
                                        title: item.title,
                                        authKey: item.authKey,
                                        closable: item.closable,
                                        header: item.header
                                    };
                                if (Ext.ClassManager.get(item.$className).prototype.isWindow) {
                                    Ext.applyIf(cfg, me.defaults);
                                }
                                if (item.requireClasses) {
                                    cfg.requireClasses = item.requireClasses;
                                }
                                items.push(cfg);
                            });
                            if (items.length > 0) {
                                Ext.apply(state, {
                                    activeItem: me.items.indexOf(me.getActiveTab()),
                                    items: items
                                });
                            }
                            return state;
                        },
                        applyState: function(state) {
                            var me = this,
                                configurations = [];
                            if (state.items && state.items.length > 0) {
                                Ext.Array.each(state.items, function(item, index) {
                                    if (index == state.activeItem) {
                                        item.activeTab = true;
                                    }
                                    configurations.push(item);
                                });
                                MdiManager.addViewsToTab(configurations, function() {
                                    delete me.statefulLock;
                                });
                            } else {
                                delete me.statefulLock;
                            }
                        },
                        addingViews: {},
                        floatable: false,
                        region: 'center',
                        publishes: [
                            'width'
                        ],
                        reference: 'mdiTabPanel',
                        stateEvents: [
                            'add',
                            'remove',
                            'tabchange'
                        ],
                        stateId: 'mdi.mditabpanel',
                        stateful: true,
                        cls: 'nbr',
                        defaults: {
                            closable: true,
                            floating: false,
                            border: true,
                            frame: false,
                            frameHeader: true,
                            resizable: false,
                            constrain: true,
                            floatable: false,
                            autoShow: false,
                            maximized: false,
                            focusOnToFront: false,
                            onEsc: Ext.emptyFn
                        },
                        bodyCls: 'mdi-tabpanel-body',
                        bodyPadding: 3,
                        frameHeader: false,
                        activeTab: 0,
                        listeners: {
                            tabchange: {
                                fn: 'onMdiTabPanelTabChange',
                                scope: 'controller'
                            },
                            render: {
                                fn: 'onTabpanelRender',
                                single: true,
                                scope: 'controller'
                            },
                            beforestatesave: 'onTabpanelBeforeStateSave',
                            beforestaterestore: 'onTabpanelBeforeStateRestore'
                        },
                        tabBar: {
                            xtype: 'tabbar',
                            reference: 'mdiTabBar',
                            ui: 'mdi-tabbar',
                            defaults: {
                                bubbleEvents: [
                                    'click'
                                ]
                            },
                            listeners: {
                                afterrender: {
                                    fn: 'onTabbarAfterRender',
                                    scope: 'controller'
                                },
                                click: {
                                    fn: 'onMdiTabClick',
                                    scope: 'controller'
                                }
                            }
                        }
                    }),
                    {
                        xtype: 'mditools',
                        reference: 'tools',
                        floating: true,
                        hidden: true,
                        listeners: {
                            topMenu: {
                                fn: 'onToolsTopMenu',
                                scope: 'controller'
                            },
                            leftMenu: {
                                fn: 'onToolsLeftMenu',
                                scope: 'controller'
                            },
                            closeAll: {
                                fn: 'onToolsCloseAll',
                                scope: 'controller'
                            }
                        }
                    },
                    {
                        xtype: 'mdii18neditor',
                        reference: 'i18nEditor',
                        floating: true,
                        closable: true,
                        closeAction: 'hide',
                        region: 'east'
                    },
                    {
                        xtype: 'mdiuserinfo',
                        reference: 'userInfo',
                        floating: true,
                        closable: true,
                        closeAction: 'hide',
                        region: 'east'
                    },
                    me.processMdiFoot({
                        xtype: 'container',
                        region: 'south',
                        reference: 'mdiFoot',
                        cls: 'mdi-footer-container',
                        layout: {
                            type: 'hbox',
                            align: 'stretch',
                            pack: 'end'
                        },
                        items: [
                            {
                                xtype: 'component',
                                cls: 'mdi-footer'
                            }
                        ]
                    })
                ]
            };
        if (instanceConfig) {
            me.getConfigurator().merge(me, config, instanceConfig);
        }
        return me.callParent([
            config
        ]);
    },
    processMdiTabPanel: function(config) {
        if (config.stateful) {
            config.statefulLock = true;
        }
        config.plugins = [
            Ext.create('Mdi.ux.TabReorderer'),
            Ext.create('Mdi.ux.TabCloseMenu')
        ];
        config.useProgressBarMask = true;
		config.stateful = false;
        return config;
    },
    processMdiLeft: function(config) {
        config.split = {
            cls: 'mdi-left-menu-splitter mdi-left-menu-collapsed',
            width: 0
        };
        return config;
    },
    processMdiFoot: function(config) {
        return config;
    },
    onTabpanelBeforeStateSave: function(stateful, state, eOpts) {
        if (stateful.statefulLock) {
            return false;
        }
    },
    onTabpanelBeforeStateRestore: function(stateful, state, eOpts) {
        if (stateful.statefulLock) {
            return false;
        }
    }
});

/*
 * File: app/view/mdi/authenticator/StandardViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.authenticator.StandardViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mdiauthenticatorstandard',
    data: {
        authentication: {}
    }
});

/*
 * File: app/view/mdi/authenticator/StandardViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.authenticator.StandardViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mdiauthenticatorstandard',
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
                success: function(response) {
                    if (response.responseText) {
                        reject(response.responseText);
                    } else {
                        resolve();
                    }
                },
                failure: function() {
                    reject('오류발생');
                }
            });
        });
    },
    onTextfieldSpecialkey: function(field, e, eOpts) {
        var me = this;
        if (e.getKey() == e.ENTER) {
            var me = this;
            me.login().then(function() {
                location.reload();
            }, function(message) {
                Ext.Msg.alert('#{주의}', message);
            });
        }
    },
    onLoginButtonClick: function(button, e, eOpts) {
        var me = this;
        me.login().then(function() {
            location.reload();
        }, function(message) {
            Ext.Msg.alert('#{주의}', message);
        });
    },
    onFormAfterRender: function(component, eOpts) {
        var me = this,
            view = me.getView();
        view.getForm().clearInvalid();
    }
});

/*
 * File: app/view/mdi/authenticator/Standard.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.authenticator.Standard', {
    extend: Ext.form.Panel,
    alias: 'widget.mdiauthenticatorstandard',
    controller: 'mdiauthenticatorstandard',
    viewModel: {
        type: 'mdiauthenticatorstandard'
    },
    border: false,
    style: {
        border: 'none'
    },
    width: 300,
    defaults: {
        height: 22
    },
    bodyCls: 'mdi-functionbar',
    fieldDefaults: {
        margin: '0 5 0 0'
    },
    layout: {
        type: 'hbox',
        align: 'stretch'
    },
    items: [
        {
            xtype: 'textfield',
            flex: 1,
            allowBlank: false,
            emptyText: 'username',
            bind: {
                value: '{authentication.j_username}'
            }
        },
        {
            xtype: 'textfield',
            flex: 1,
            inputType: 'password',
            allowBlank: false,
            emptyText: 'password',
            bind: {
                value: '{authentication.j_password}'
            },
            listeners: {
                specialkey: 'onTextfieldSpecialkey'
            }
        },
        {
            xtype: 'button',
            width: 70,
            text: 'LOGIN',
            listeners: {
                click: 'onLoginButtonClick'
            }
        }
    ],
    listeners: {
        afterrender: 'onFormAfterRender'
    }
});

/*
 * File: app/view/mdi/popup/MdiTabOverflowPopupViewModel.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.popup.MdiTabOverflowPopupViewModel', {
    extend: Ext.app.ViewModel,
    alias: 'viewmodel.mdipopupmditaboverflowpopup',
    stores: {
        overflowStore: {
            proxy: {
                type: 'memory'
            },
            fields: [
                {
                    type: 'string',
                    name: 'title'
                },
                {
                    type: 'string',
                    name: 'classpath'
                },
                {
                    type: 'string',
                    name: 'authKey'
                }
            ]
        }
    }
});

/*
 * File: app/view/mdi/popup/MdiTabOverflowPopupViewController.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.popup.MdiTabOverflowPopupViewController', {
    extend: Ext.app.ViewController,
    alias: 'controller.mdipopupmditaboverflowpopup',
    init: function() {
        var me = this,
            view = me.getView();
        Ext.apply(view, {
            loadTabs: Ext.Function.bind(me.loadTabs, me)
        });
    },
    loadTabs: function(tabpanel) {
        var me = this,
            overflowStore = me.getStore('overflowStore');
        overflowStore.loadData((function() {
            var items = [];
            Ext.Array.each(tabpanel.getTabBar().getRefItems(), function(tab) {
                var card = tab.card;
                if (card.closable) {
                    items.push({
                        title: card.title,
                        classpath: card.classpath,
                        authKey: card.authKey
                    });
                }
            });
            return items;
        }()));
    },
    onGridpanelItemClick: function(dataview, record, item, index, e, eOpts) {
        var me = this,
            view = me.getView();
        MdiManager.closeView(record.get('classpath'));
        view.fireEvent('addview');
        view.close();
    }
});

/*
 * File: app/view/mdi/popup/MdiTabOverflowPopup.js
 *
 * This file was generated by Sencha Architect
 * http://www.sencha.com/products/architect/
 *
 * This file requires use of the Ext JS 5.0.x library, under independent license.
 * License of Sencha Architect does not include license for Ext JS 5.0.x. For more
 * details see http://www.sencha.com/license or contact redacted@example.invalid.
 *
 * This file will be auto-generated each and everytime you save your project.
 *
 * Do NOT hand edit this file.
 */
Ext.define('Mdi.view.mdi.popup.MdiTabOverflowPopup', {
    extend: Ext.window.Window,
    alias: 'widget.mdipopupmditaboverflowpopup',
    controller: 'mdipopupmditaboverflowpopup',
    viewModel: {
        type: 'mdipopupmditaboverflowpopup'
    },
    autoShow: true,
    cls: 'mdi-tab-overflow',
    maxHeight: 300,
    minHeight: 150,
    resizable: false,
    width: 320,
    title: '#{알림}',
    modal: true,
    layout: {
        type: 'vbox',
        align: 'stretch',
        pack: 'center'
    },
    initConfig: function(instanceConfig) {
    	var me = this,
	        config = {
	            items: [
	                me.processOverflowLabel({
	                    xtype: 'label',
	                    reference: 'overflowLabel',
	                    cls: 'mdi-tab-overflow-label',
	                    padding: 10
	                }),
	                {
	                    xtype: 'component',
	                    cls: 'mdi-tab-overflow-separator'
	                },
	                me.processOverflowGrid({
	                    xtype: 'gridpanel',
	                    flex: 1,
	                    reference: 'overflowGrid',
	                    maxHeight: 200,
	                    minHeight: 100,
	                    padding: '5 0 0',
	                    header: false,
	                    title: 'My Grid Panel',
	                    hideHeaders: true,
	                    rowLines: false,
	                    bind: {
	                        store: '{overflowStore}'
	                    },
	                    columns: [
	                        {
	                            xtype: 'gridcolumn',
	                            renderer: function(value, metaData, record, rowIndex, colIndex, store, view) {
	                                return Ext.String.format('<div class="tab"></div>{0}', value);
	                            },
	                            dataIndex: 'title',
	                            text: 'String',
	                            flex: 1
	                        }
	                    ],
	                    listeners: {
	                        itemclick: 'onGridpanelItemClick'
	                    }
	                }),
	                // 확인버튼 추가 김형민
	                {
	                    xtype: 'button',
	                    text: '#{확인}',
	                    handler: function() {
	                        this.up('window').close();
	                    }
	                },
	            ]
	        };
        if (instanceConfig) {
            me.getConfigurator().merge(me, config, instanceConfig);
        }
        return me.callParent([
            config
        ]);
    },
    processOverflowLabel: function(config) {
        var me = this;
        config.text = Ext.String.format('#{탭 생성 개수는 {0}개로 한정되어 있습니다.\n아래 목록 중 닫기 대상을 선택하시기 바랍니다.}', me.initialConfig.mdiTabOverflow);
        return config;
    },
    processOverflowGrid: function(config) {
        config.enableLocking = false;
        return config;
    },
    processTabOverflowGrid: function(config) {
        config.enableLocking = false;
        return config;
    }
});


Ext.define('Site.override.ServerExceptionHandler',{
	override : 'Cmmn.ServerExceptionHandler',
	goToLogin: function() {
		
		//location.reload(); 원래 로직
		if(isForeign){ // userType에 따라 외자 로그인 외자 로그인페이지중 어디로 이동할지 결정
			location.href =  '/oversea.do';
		}
		else{
			location.reload(); //원래 로직
		}
	}
});

Ext.define("Mdi.view.mdi.I18nEditorViewController.I18n", {override : "Mdi.view.mdi.I18nEditorViewController", i18n : ["\uc624\ub958","\ub2e4\uad6d\uc5b4 \uc815\ubcf4 \uc870\ud68c\uc2dc \uc624\ub958\uac00 \ubc1c\uc0dd\ud558\uc600\uc2b5\ub2c8\ub2e4.","\uc54c\ub9bc","\ub2e4\uad6d\uc5b4 \uc815\ubcf4 \uc800\uc7a5 \ub418\uc5c8\uc2b5\ub2c8\ub2e4.","\uc624\ub958","\ub2e4\uad6d\uc5b4 \uc815\ubcf4 \uc800\uc7a5\uc2dc \uc624\ub958\uac00 \ubc1c\uc0dd\ud558\uc600\uc2b5\ub2c8\ub2e4.","key \uac12\uc744 \uc785\ub825\ud574\uc8fc\uc138\uc694"]});Ext.define("Mdi.view.mdi.I18nEditor.I18n", {override : "Mdi.view.mdi.I18nEditor", i18n : ["internationalization","locale","add","save","status","key","value"]});Ext.define("Mdi.view.mdi.MyAppViewController.I18n", {override : "Mdi.view.mdi.MyAppViewController", i18n : ["\ud3f4\ub354 \uc0dd\uc131","\uc774\ub984 \ubc14\uafb8\uae30","\uc0ad\uc81c","\uc0c8\ud3f4\ub354","\ud3f4\ub354 \uc774\ub984\uc744 \uc785\ub825\ud574 \uc8fc\uc2ed\uc2dc\uc624:","\uc0c8\ud3f4\ub354","\uc774\ub984 \ubc14\uafb8\uae30","\uc0c8 \uc774\ub984\uc744 \uc785\ub825\ud574 \uc8fc\uc2ed\uc2dc\uc624:","\uc0ad\uc81c","\ud3f4\ub354","\uc571","\uc571\uc2a4\ud1a0\uc5b4","\uc124\uce58\uc911...","\uc124\uce58","\ub9c8\uc774\uc571","\uc0c8\ub85c\uace0\uce68","\uc571\uc2a4\ud1a0\uc5b4","\uc804\uccb4","\uc804\uccb4"]});Ext.define("Mdi.view.mdi.MyApp.I18n", {override : "Mdi.view.mdi.MyApp", i18n : ["\ub9c8\uc774\uc571","\uc124\uce58\ub428","\uc124\uce58"]});Ext.define("Mdi.view.mdi.Tools.I18n", {override : "Mdi.view.mdi.Tools", i18n : ["Left \uba54\ub274 \ud65c\uc131\ud654","Top \uba54\ub274 \ud65c\uc131\ud654","\ubaa8\ub4e0 \ud654\uba74 \ub2eb\uae30"]});Ext.define("Mdi.view.mdi.TopViewController.I18n", {override : "Mdi.view.mdi.TopViewController", i18n : ["\ud655\uc778","\uc5b8\uc5b4\ub97c \ubcc0\uacbd \ud558\uc2dc\ub824\uba74 \ud398\uc774\uc9c0\ub97c \uc0c8\ub85c\uace0\uce68 \ub429\ub2c8\ub2e4.\n\ubcc0\uacbd\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?","\uc624\ub958","\uc0ac\uc6a9\uc790 \ub85c\ucf00\uc77c \ubcc0\uacbd\uc2dc \uc624\ub958\uac00 \ubc1c\uc0dd\ud558\uc600\uc2b5\ub2c8\ub2e4.","\uc624\ub958","\uc0ac\uc6a9\uc790 \ub85c\ucf00\uc77c \uc870\ud68c\uc2dc \uc624\ub958\uac00 \ubc1c\uc0dd\ud558\uc600\uc2b5\ub2c8\ub2e4.","\ud655\uc778","\ub85c\uadf8\uc544\uc6c3 \ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?"]});Ext.define("Mdi.view.mdi.Top.I18n", {override : "Mdi.view.mdi.Top", i18n : ["My App","Home","My Profile","Alarm On/Off","View Memo","Catalog Search","Shopping Cart","Personal Setup","Logout","Top Menu Toggle"]});Ext.define("Mdi.view.mdi.UserInfoViewController.I18n", {override : "Mdi.view.mdi.UserInfoViewController", i18n : ["\uc774\uba54\uc77c \ud615\uc2dd\uc5d0 \ub9de\uac8c \uc785\ub825\ud558\uc138\uc694.","{0} \uc744(\ub97c) \uc785\ub825\ud558\uc138\uc694.","\ube44\ubc00\ubc88\ud638 \ud655\uc778\uc744 \ud574\uc57c\ud569\ub2c8\ub2e4.","\uc800\uc7a5 \ud558\uc600\uc2b5\ub2c8\ub2e4."]});Ext.define("Mdi.view.mdi.UserInfo.I18n", {override : "Mdi.view.mdi.UserInfo", i18n : ["\uc0ac\uc6a9\uc790 \uc815\ubcf4","\uc218\uc815","\uc218\uc815\ucde8\uc18c","\uc800\uc7a5","\ub2eb\uae30","\uc0ac\uc6a9\uc790 ID","\uc774\ub984","\uc774\ub984(\uc601\ubb38)","\ube44\ubc00\ubc88\ud638","\ube44\ubc00\ubc88\ud638 \ud655\uc778","\ud68c\uc0ac","\ubd80\uc11c","\uc774\uba54\uc77c","\uc804\ud654\ubc88\ud638","H.P \ubc88\ud638","Fax \ubc88\ud638"]});Ext.define("Mdi.view.mdi.popup.ChangePasswordPopupViewController.I18n", {override : "Mdi.view.mdi.popup.ChangePasswordPopupViewController", i18n : ["\uc54c\ub9bc","\uc0c8 \ube44\ubc00\ubc88\ud638\ub97c \uc785\ub825\ud558\uc138\uc694.","\uc54c\ub9bc","\uc0c8 \ube44\ubc00\ubc88\ud638 \ud655\uc778\uc744 \uc785\ub825\ud558\uc138\uc694.","\uc54c\ub9bc","'\uc0c8 \ube44\ubc00\ubc88\ud638'\uc640 '\uc0c8 \ube44\ubc00\ubc88\ud638 \ud655\uc778' \uac12\uc774 \ub2e4\ub985\ub2c8\ub2e4.","\ube44\ubc00\ubc88\ud638 \uc800\uc7a5\uc5d0 \uc131\uacf5\ud558\uc600\uc2b5\ub2c8\ub2e4.","\ube44\ubc00\ubc88\ud638 \uc800\uc7a5\uc5d0 \uc2e4\ud328\ud558\uc600\uc2b5\ub2c8\ub2e4.","\ube44\ubc00\ubc88\ud638 \uc800\uc7a5\uc5d0 \uc2e4\ud328\ud558\uc600\uc2b5\ub2c8\ub2e4."]});Ext.define("Mdi.view.mdi.popup.ChangePasswordPopup.I18n", {override : "Mdi.view.mdi.popup.ChangePasswordPopup", i18n : ["\ube44\ubc00\ubc88\ud638 \ubcc0\uacbd","\uc800\uc7a5","\ub2eb\uae30","\ube44\ubc00\ubc88\ud638 \ubcc0\uacbd","\uc0c8 \ube44\ubc00\ubc88\ud638","\uc0c8 \ube44\ubc00\ubc88\ud638 \ud655\uc778"]});Ext.define("Mdi.view.mdi.popup.LatestAccessUserInfo.I18n", {override : "Mdi.view.mdi.popup.LatestAccessUserInfo", i18n : ["\ucd5c\uadfc \uc811\uc18d \uc815\ubcf4","\uc0ac\uc6a9\uc790 \uc544\uc774\ub514","\ucd5c\uadfc \uc811\uc18d \uc77c\uc2dc","\ucd5c\uadfc \uc811\uc18d \uc544\uc774\ud53c"]});Ext.define("Mdi.view.mdi.ViewportViewController.I18n", {override : "Mdi.view.mdi.ViewportViewController", i18n : ["\uc624\ub958","\uc778\uc99d \uc5ec\ubd80 \uc870\ud68c\uc2dc \uc624\ub958 \ubc1c\uc0dd\ud558\uc600\uc2b5\ub2c8\ub2e4.","\ube44\ubc00\ubc88\ud638 \ubcc0\uacbd\uc8fc\uae30 \ub9cc\ub8cc","\uc0c8 \ube44\ubc00\ubc88\ud638 \ub4f1\ub85d","\uce74\ud0c8\ub85c\uadf8 \uad6c\ub9e4","\uc7a5\ubc14\uad6c\ub2c8","\ud658\uacbd\uc124\uc815"]});Ext.define("Mdi.view.mdi.authenticator.StandardViewController.I18n", {override : "Mdi.view.mdi.authenticator.StandardViewController", i18n : ["\uc8fc\uc758","\ub85c\uadf8\uc778 \ub370\uc774\ud130\uac00 \uc720\ud6a8\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.","\uc8fc\uc758","\uc8fc\uc758"]});Ext.define("Mdi.view.mdi.popup.MdiTabOverflowPopup.I18n", {override : "Mdi.view.mdi.popup.MdiTabOverflowPopup", i18n : ["\uc54c\ub9bc","\ud0ed \uc0dd\uc131 \uac1c\uc218\ub294 {0}\uac1c\ub85c \ud55c\uc815\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4.\n\uc544\ub798 \ubaa9\ub85d \uc911 \ub2eb\uae30 \ub300\uc0c1\uc744 \uc120\ud0dd\ud558\uc2dc\uae30 \ubc14\ub78d\ub2c8\ub2e4."]});(function(definitions){
									Ext.iterate(definitions, function(className, definition){
										var clazz = Ext.ClassManager.get(className);
										var requires = [];
										Ext.each(definition.requires, function(require){
											requires.push(Ext.ClassManager.get(require));
										});
										if(clazz){Ext.override(clazz, {requires : requires});};
									});
								})(							
							{
  "Mdi.view.mdi.authenticator.StandardViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel"
    ]
  },
  "Mdi.controller.Manager": {
    "uses": [],
    "requires": [
      "Ext.Base",
      "Mdi.ux.IFrame"
    ]
  },
  "Mdi.view.mdi.authenticator.Standard": {
    "uses": [],
    "requires": [
      "Ext.form.Panel",
      "Mdi.view.mdi.authenticator.StandardViewModel",
      "Mdi.view.mdi.authenticator.StandardViewController",
      "Ext.form.field.Text",
      "Ext.button.Button"
    ]
  },
  "Mdi.view.mdi.TopViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel"
    ]
  },
  "Mdi.view.mdi.Top": {
    "uses": [],
    "requires": [
      "Ext.container.Container",
      "Mdi.view.mdi.TopViewModel",
      "Mdi.view.mdi.TopViewController",
      "Ext.toolbar.Toolbar",
      "Ext.toolbar.Spacer",
      "Ext.button.Button",
      "Ext.menu.Menu",
      "Ext.menu.Item",
      "Ext.toolbar.Breadcrumb",
      "Ext.form.Label",
      "Mdi.store.Menu",
      "Mdi.store.Locale",
      "Mdi.model.Setting"
    ]
  },
  "Mdi.view.mdi.popup.LatestAccessUserInfoViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel"
    ]
  },
  "Mdi.view.mdi.Viewport": {
    "uses": [],
    "requires": [
      "Ext.container.Viewport",
      "Mdi.view.mdi.ViewportViewModel",
      "Mdi.view.mdi.ViewportViewController",
      "Mdi.view.mdi.Top",
      "Mdi.view.mdi.Left",
      "Mdi.view.mdi.Tools",
      "Mdi.view.mdi.I18nEditor",
      "Mdi.view.mdi.UserInfo",
      "Ext.tab.Panel",
      "Ext.tab.Bar",
      "Ext.tree.Panel",
      "Ext.toolbar.Toolbar",
      "Mdi.ux.TabReorderer",
      "Mdi.ux.TabCloseMenu",
      "Etna.security.Manager",
      "Etna.i18n.Manager",
      "Etna.data.Manager",
      "Mdi.controller.Manager",
      "Mdi.store.Menu",
      "Mdi.store.Locale",
      "Mdi.model.Setting",
      "Mdi.store.UnauthorizedMenu"
    ]
  },
  "Mdi.view.mdi.ViewportViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel",
      "Ext.app.bind.Formula"
    ]
  },
  "Mdi.view.mdi.Tools": {
    "uses": [],
    "requires": [
      "Ext.toolbar.Toolbar",
      "Mdi.view.mdi.ToolsViewModel",
      "Mdi.view.mdi.ToolsViewController",
      "Ext.button.Button"
    ]
  },
  "Mdi.view.mdi.ToolsViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.view.mdi.popup.ChangePasswordPopupViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel"
    ]
  },
  "Mdi.view.mdi.TopViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.model.App": {
    "uses": [],
    "requires": [
      "Ext.data.Model",
      "Ext.data.field.String",
      "Ext.data.field.Integer",
      "Ext.data.field.Boolean"
    ]
  },
  "Mdi.model.Menu": {
    "uses": [],
    "requires": [
      "Ext.data.Model",
      "Ext.data.field.String",
      "Ext.data.field.Boolean",
      "Ext.data.field.Integer"
    ]
  },
  "Mdi.model.I18n": {
    "uses": [],
    "requires": [
      "Ext.data.Model",
      "Ext.data.field.String"
    ]
  },
  "Mdi.store.UnauthorizedMenu": {
    "uses": [],
    "requires": [
      "Ext.data.Store",
      "Mdi.model.Menu",
      "Ext.data.proxy.Rest",
      "Ext.data.reader.Json"
    ]
  },
  "Mdi.view.mdi.I18nEditorViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel",
      "Ext.data.Store",
      "Ext.data.proxy.Rest",
      "Ext.data.ChainedStore",
      "Mdi.model.I18n"
    ]
  },
  "Mdi.view.mdi.TopDropMenuViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.view.mdi.I18nEditor": {
    "uses": [],
    "requires": [
      "Ext.panel.Panel",
      "Mdi.view.mdi.I18nEditorViewModel",
      "Mdi.view.mdi.I18nEditorViewController",
      "Ext.toolbar.Toolbar",
      "Ext.form.field.ComboBox",
      "Ext.toolbar.Spacer",
      "Ext.button.Button",
      "Ext.grid.Panel",
      "Etna.grid.column.Status",
      "Ext.grid.View",
      "Ext.grid.plugin.CellEditing"
    ]
  },
  "Mdi.view.mdi.UserInfoViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.ux.TabReorderer": {
    "uses": [],
    "requires": [
      "Mdi.ux.BoxReorderer"
    ]
  },
  "Mdi.store.Menu": {
    "uses": [],
    "requires": [
      "Ext.data.TreeStore",
      "Mdi.model.Menu",
      "Ext.data.proxy.Rest",
      "Ext.data.reader.Json",
      "Ext.util.Sorter",
      "Mdi.model.Setting"
    ]
  },
  "Mdi.ux.TabScrollerMenu": {
    "uses": [],
    "requires": [
      "Ext.menu.Menu"
    ]
  },
  "Mdi.view.mdi.Left": {
    "uses": [],
    "requires": [
      "Ext.tree.Panel",
      "Mdi.view.mdi.LeftViewModel",
      "Mdi.view.mdi.LeftViewController",
      "Ext.tree.View",
      "Ext.tree.Column",
      "Etna.grid.plugin.Stateful",
      "Mdi.store.Menu"
    ]
  },
  "Mdi.view.mdi.MyAppViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.view.mdi.ViewportViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController",
      "Mdi.ux.IFrame"
    ]
  },
  "Mdi.view.mdi.MyApp": {
    "uses": [],
    "requires": [
      "Ext.window.Window",
      "Mdi.view.mdi.MyAppViewModel",
      "Mdi.view.mdi.MyAppViewController",
      "Ext.tree.Panel",
      "Ext.tree.View",
      "Ext.toolbar.Toolbar",
      "Ext.button.Button",
      "Ext.toolbar.Breadcrumb",
      "Ext.XTemplate",
      "Mdi.model.App"
    ]
  },
  "Mdi.view.mdi.LeftViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel",
      "Ext.data.TreeStore",
      "Ext.data.proxy.Memory"
    ]
  },
  "Mdi.view.mdi.UserInfo": {
    "uses": [],
    "requires": [
      "Ext.panel.Panel",
      "Mdi.view.mdi.UserInfoViewModel",
      "Mdi.view.mdi.UserInfoViewController",
      "Ext.toolbar.Toolbar",
      "Ext.toolbar.Fill",
      "Ext.button.Button",
      "Ext.form.Panel",
      "Ext.form.field.Text"
    ]
  },
  "Mdi.store.Locale": {
    "uses": [],
    "requires": [
      "Ext.data.Store",
      "Ext.data.field.String",
      "Ext.data.proxy.Rest"
    ]
  },
  "Mdi.view.mdi.popup.ChangePasswordPopup": {
    "uses": [],
    "requires": [
      "Ext.window.Window",
      "Mdi.view.mdi.popup.ChangePasswordPopupViewModel",
      "Mdi.view.mdi.popup.ChangePasswordPopupViewController",
      "Ext.toolbar.Toolbar",
      "Ext.toolbar.Spacer",
      "Ext.button.Button",
      "Ext.form.Panel",
      "Ext.form.field.Text"
    ]
  },
  "Mdi.ux.TabCloseMenu": {
    "uses": [],
    "requires": []
  },
  "Mdi.model.Setting": {
    "uses": [],
    "requires": [
      "Ext.data.Model",
      "Ext.data.field.Boolean",
      "Ext.data.field.String"
    ]
  },
  "Mdi.view.mdi.popup.LatestAccessUserInfo": {
    "uses": [],
    "requires": [
      "Ext.window.Window",
      "Mdi.view.mdi.popup.LatestAccessUserInfoViewModel",
      "Mdi.view.mdi.popup.LatestAccessUserInfoViewController",
      "Ext.form.Panel",
      "Ext.form.FieldContainer",
      "Ext.form.field.Text"
    ]
  },
  "Mdi.ux.BoxReorderer": {
    "uses": [],
    "requires": [
      "Ext.dd.DD"
    ]
  },
  "Mdi.view.mdi.LeftViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.view.mdi.popup.MdiTabOverflowPopupViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel",
      "Ext.data.Store",
      "Ext.data.proxy.Memory",
      "Ext.data.field.String"
    ]
  },
  "Mdi.view.mdi.authenticator.StandardViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.view.mdi.popup.LatestAccessUserInfoViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.ux.IFrame": {
    "uses": [],
    "requires": [
      "Ext.Component"
    ]
  },
  "Mdi.view.mdi.MyAppViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel",
      "Ext.data.TreeStore",
      "Ext.data.proxy.Memory",
      "Ext.data.proxy.Direct",
      "Ext.data.reader.Json",
      "Ext.util.Sorter"
    ]
  },
  "Mdi.view.mdi.popup.MdiTabOverflowPopup": {
    "uses": [],
    "requires": [
      "Ext.window.Window",
      "Mdi.view.mdi.popup.MdiTabOverflowPopupViewModel",
      "Mdi.view.mdi.popup.MdiTabOverflowPopupViewController",
      "Ext.form.Label",
      "Ext.grid.Panel",
      "Ext.grid.column.Column",
      "Ext.grid.View",
      "Mdi.controller.Manager"
    ]
  },
  "Mdi.view.mdi.TopDropMenu": {
    "uses": [],
    "requires": [
      "Ext.view.View",
      "Mdi.view.mdi.TopDropMenuViewModel",
      "Mdi.view.mdi.TopDropMenuViewController",
      "Ext.XTemplate"
    ]
  },
  "Mdi.view.mdi.TopDropMenuViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel"
    ]
  },
  "Mdi.view.mdi.I18nEditorViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.view.mdi.UserInfoViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel"
    ]
  },
  "Mdi.view.mdi.ToolsViewModel": {
    "uses": [],
    "requires": [
      "Ext.app.ViewModel"
    ]
  },
  "Mdi.view.mdi.popup.MdiTabOverflowPopupViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  },
  "Mdi.view.mdi.popup.ChangePasswordPopupViewController": {
    "uses": [],
    "requires": [
      "Ext.app.ViewController"
    ]
  }
}
);