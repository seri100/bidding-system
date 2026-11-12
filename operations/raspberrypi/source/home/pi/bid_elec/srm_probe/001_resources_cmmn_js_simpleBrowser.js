var SimpleBrowser = SimpleBrowser || {};
SimpleBrowser.env || (SimpleBrowser.env = {});
SimpleBrowser.apply = function(object, config, defaults) {
    if (defaults) {
        SimpleBrowser.apply(object, defaults);
    }
    if (object && config && typeof config === 'object') {
        var i, j, k;
        for (i in config) {
            object[i] = config[i];
        }
        if (enumerables) {
            for (j = enumerables.length; j--;) {
                k = enumerables[j];
                if (config.hasOwnProperty(k)) {
                    object[k] = config[k];
                }
            }
        }
    }
    return object;
};
(function() {
  var  ExtObject = SimpleBrowser.Object = {
    getKey: function(object, value) {
        for (var property in object) {
            if (object.hasOwnProperty(property) && object[property] === value) {
                return property;
            }
        }
        return null;
    },
    getValues: function(object) {
        var values = [],
            property;

        for (property in object) {
            if (object.hasOwnProperty(property)) {
                values.push(object[property]);
            }
        }
        return values;
    },
    equals: (function() {
        var check = function(o1, o2) {
            var key;
        
            for (key in o1) {
                if (o1.hasOwnProperty(key)) {
                    if (o1[key] !== o2[key]) {
                        return false;
                    }    
                }
            }    
            return true;
        };
        
        return function(object1, object2) {
            if (object1 === object2) {
                return true;
            } if (object1 && object2) {
                return check(object1, object2) && check(object2, object1);  
            } else if (!object1 && !object2) {
                return object1 === object2;
            } else {
                return false;
            }
        };
    })()
};
SimpleBrowser.merge = SimpleBrowser.Object.merge;
SimpleBrowser.mergeIf = SimpleBrowser.Object.mergeIf;
}());

(function() {
	    var checkVerTemp = [''],
	        endOfVersionRe = /([^\d\.])/,
	        notDigitsRe = /[^\d]/g,
	        plusMinusRe = /[\-+]/g,
	        stripRe = /\s/g,
	        underscoreRe = /_/g,
	        Version;

	    SimpleBrowser.Version = Version = function(version, defaultMode) {
	            var me = this,
	                padModes = me.padModes,
	                ch, i, pad, parts, release, releaseStartIndex, ver;

	            if (version.isVersion) {
	                version = version.version;
	            }
	            me.version = ver = String(version).toLowerCase().
	                                    replace(underscoreRe, '.').replace(plusMinusRe, '');

	            ch = ver.charAt(0);
	            if (ch in padModes) {
	                ver = ver.substring(1);
	                pad = padModes[ch];
	            } else {
	                pad = defaultMode ? padModes[defaultMode] : 0; // careful - NaN is falsey!
	            }
	            me.pad = pad;
	            releaseStartIndex = ver.search(endOfVersionRe);
	            me.shortVersion = ver;

	            if (releaseStartIndex !== -1) {
	                me.release = release = ver.substr(releaseStartIndex, version.length);
	                me.shortVersion = ver.substr(0, releaseStartIndex);
	                release = Version.releaseValueMap[release] || release;
	            }

	            me.releaseValue = release || pad;
	            me.shortVersion = me.shortVersion.replace(notDigitsRe, '');

	            me.parts = parts = ver.split('.');
	            for (i = parts.length; i--; ) {
	                parts[i] = parseInt(parts[i], 10);
	            }
	            if (pad === Infinity) {
	                parts.push(pad);
	            }
	            me.major = parts[0] || pad;
	            me.minor = parts[1] || pad;
	            me.patch = parts[2] || pad;
	            me.build = parts[3] || pad;
	            return me;
	    };

	    Version.prototype = {
	        isVersion: true,
	        padModes: {
	            '~': NaN,
	            '^': Infinity
	        },
	        toString: function() {
	            return this.version;
	        },
	        valueOf: function() {
	            return this.version;
	        },
	        getMajor: function() {
	            return this.major;
	        },
	        getMinor: function() {
	            return this.minor;
	        },
	        isGreaterThan: function(target) {
	            return this.compareTo(target) > 0;
	        },
	        isGreaterThanOrEqual: function(target) {
	            return this.compareTo(target) >= 0;
	        },
	        isLessThan: function(target) {
	            return this.compareTo(target) < 0;
	        },
	        isLessThanOrEqual: function(target) {
	            return this.compareTo(target) <= 0;
	        },
	        equals: function(target) {
	            return this.compareTo(target) === 0;
	        },
	        match: function(target) {
	            target = String(target);
	            return this.version.substr(0, target.length) === target;
	        },
	        toArray: function() {
	            var me = this;
	            return [me.getMajor(), me.getMinor(), me.getPatch(), me.getBuild(), me.getRelease()];
	        },
	        getShortVersion: function() {
	            return this.shortVersion;
	        },
	        gt: function (target) {
	            return this.compareTo(target) > 0;
	        },
	        lt: function (target) {
	            return this.compareTo(target) < 0;
	        },
	        gtEq: function (target) {
	            return this.compareTo(target) >= 0;
	        },
	        ltEq: function (target) {
	            return this.compareTo(target) <= 0;
	        }
	    };

	    SimpleBrowser.apply(SimpleBrowser, {
	        compatVersions: {},
	        versions: {},
	        lastRegisteredVersion: null,
	        setVersion: function (packageName, version) {
	            SimpleBrowser.lastRegisteredVersion = Version.set(SimpleBrowser.versions, packageName, version);
	            return this;
	        },
	        getVersion: function (packageName) {
	            var versions = SimpleBrowser.versions;

	            if (!packageName) {
	                return versions.ext || versions.touch || versions.core;
	            }

	            return versions[Version.aliases.from[packageName] || packageName];
	        },
	        checkVersion: function (specs, matchAll) {
	            var isArray = SimpleBrowser.isArray(specs),
	                aliases = Version.aliases.from,
	                compat = isArray ? specs : checkVerTemp,
	                length = compat.length,
	                versions = SimpleBrowser.versions,
	                frameworkVer = versions.ext || versions.touch,
	                i, index, matches, minVer, maxVer, packageName, spec, range, ver;

	            if (!isArray) {
	                checkVerTemp[0] = specs;
	            }

	            for (i = 0; i < length; ++i) {
	                if (!SimpleBrowser.isString(spec = compat[i])) {
	                    matches = SimpleBrowser.checkVersion(spec.and || spec.or, !spec.or);
	                    if (spec.not) {
	                        matches = !matches;
	                    }
	                } else {
	                    if (spec.indexOf(' ') >= 0) {
	                        spec = spec.replace(stripRe, '');
	                    }

	                    index = spec.indexOf('@');
	                    if (index < 0) {
	                        range = spec;
	                        ver = frameworkVer;
	                    } else {
	                        packageName = spec.substring(0, index);
	                        if (!(ver = versions[aliases[packageName] || packageName])) {
	                            if (matchAll) {
	                                return false;
	                            }
	                            continue;
	                        }
	                        range = spec.substring(index+1);
	                    }
	                    index = range.indexOf('-');
	                    if (index < 0) {
	                        if (range.charAt(index = range.length - 1) === '+') {
	                            minVer = range.substring(0, index);
	                            maxVer = null;
	                        } else {
	                            minVer = maxVer = range;
	                        }
	                    } else if (index > 0) {
	                        minVer = range.substring(0, index);
	                        maxVer = range.substring(index+1); // may be empty
	                    } else {
	                        minVer = null;
	                        maxVer = range.substring(index+1);
	                    }

	                    matches = true;
	                    if (minVer) {
	                        minVer = new Version(minVer, '~'); // prefix matching
	                        matches = minVer.ltEq(ver);
	                    }
	                    if (matches && maxVer) {
	                        maxVer = new Version(maxVer, '~'); // prefix matching
	                        matches = maxVer.gtEq(ver);
	                    }
	                } // string spec

	                if (matches) {
	                    if (!matchAll) {
	                        return true;
	                    }
	                } else if (matchAll) {
	                    return false;
	                }
	            }
	            return !!matchAll;
	        }
	    }); // End Versioning
	}());

	(function (manifest){
	    var packages = (manifest && manifest.packages) || {},
	        compat = manifest && manifest.compatibility,
	        name, pkg;
	    

	})(SimpleBrowser.manifest);

var global = this,
objectPrototype = Object.prototype,
toString = objectPrototype.toString,
enumerables = [
               'valueOf', 'toLocaleString', 'toString', 'constructor'],
emptyFn = function () {},
privateFn = function () {},
identityFn = function(o) { return o; },


manifest = SimpleBrowser.manifest || {},
i,
iterableRe = /\[object\s*(?:Array|Arguments|\w*Collection|\w*List|HTML\s+document\.all\s+class)\]/,
MSDateRe = /^\\?\/Date\(([-+])?(\d+)(?:[+-]\d{4})?\)\\?\/$/;

SimpleBrowser.global = global;
SimpleBrowser.env.Browser = function (userAgent, publish) {

    var me = this,
        browserPrefixes = me.browserPrefixes,
        enginePrefixes = me.enginePrefixes,
        browserMatch = userAgent.match(new RegExp('((?:' + 
                SimpleBrowser.Object.getValues(browserPrefixes).join(')|(?:') + '))([\\w\\._]+)')),
        engineMatch = userAgent.match(new RegExp('((?:' + 
                SimpleBrowser.Object.getValues(enginePrefixes).join(')|(?:') + '))([\\w\\._]+)')),
        browserNames = me.browserNames,
        browserName = browserNames.other,
        engineNames = me.engineNames,
        engineName = engineNames.other,
        browserVersion = '',
        engineVersion = '',
        majorVer = '',
        isWebView = false,
        i, prefix, mode, name, maxIEVersion;

    /**
     * @property {String}
     * Browser User Agent string.
     */
    me.userAgent = userAgent;

    if (browserMatch) {
        browserName = browserNames[SimpleBrowser.Object.getKey(browserPrefixes, browserMatch[1])];
        //<feature legacyBrowser>
        if (browserName === 'Safari' && /^Opera/.test(userAgent)) {
            // Prevent Opera 12 and earlier from being incorrectly reported as Safari
            browserName = 'Opera';
        }
        //</feature>
        browserVersion = new SimpleBrowser.Version(browserMatch[2]);
    }

    if (engineMatch) {
        engineName = engineNames[SimpleBrowser.Object.getKey(enginePrefixes, engineMatch[1])];
        engineVersion = new SimpleBrowser.Version(engineMatch[2]);
    }

    if (engineName == 'Trident' && browserName != 'IE') {
        browserName = 'IE';
        var version = userAgent.match(/.*rv:(\d+.\d+)/);
        if (version && version.length) {
            version = version[1];
            browserVersion = new SimpleBrowser.Version(version);
        }
    }
    if (userAgent.match(/FB/) && browserName == "Other") {
        browserName = browserNames.safari;
        engineName = engineNames.webkit;
    }

    if (userAgent.match(/Android.*Chrome/g)) {
        browserName = 'ChromeMobile';
    }

    if (userAgent.match(/OPR/)) {
        browserName = 'Opera';
        browserMatch = userAgent.match(/OPR\/(\d+.\d+)/);
        browserVersion = new SimpleBrowser.Version(browserMatch[1]);
    }

    SimpleBrowser.apply(this, {
        engineName: engineName,
        engineVersion: engineVersion,
        name: browserName,
        version: browserVersion
    });

    this.setFlag(browserName, true, publish); // e.g., Ext.isIE

    if (browserVersion) {
        majorVer = browserVersion.getMajor() || '';
        if (me.is.IE) {
            majorVer = parseInt(majorVer, 10);
            mode = document.documentMode;

            if (mode == 7 || (majorVer == 7 && mode != 8 && mode != 9 && mode != 10)) {
                majorVer = 7;
            } else if (mode == 8 || (majorVer == 8 && mode != 8 && mode != 9 && mode != 10)) {
                majorVer = 8;
            } else if (mode == 9 || (majorVer == 9 && mode != 7 && mode != 8 && mode != 10)) {
                majorVer = 9;
            } else if (mode == 10 || (majorVer == 10 && mode != 7 && mode != 8 && mode != 9)) {
                majorVer = 10;
            } else if (mode == 11 || (majorVer == 11 && mode != 7 && mode != 8 && mode != 9 && mode != 10)) {
                majorVer = 11;
            }
            maxIEVersion = Math.max(majorVer, 11);
            for (i = 7; i <= maxIEVersion; ++i) {
                prefix = 'isIE' + i; 
                if (majorVer <= i) {
                    SimpleBrowser[prefix + 'm'] = true;
                }

                if (majorVer === i) {
                    SimpleBrowser[prefix] = true;
                }

                if (majorVer >= i) {
                    SimpleBrowser[prefix + 'p'] = true;
                }
            }
        }

        if (me.is.Opera && parseInt(majorVer, 10) <= 12) {
            SimpleBrowser.isOpera12m = true;
        }
        SimpleBrowser.chromeVersion = SimpleBrowser.isChrome ? majorVer : 0;
        SimpleBrowser.firefoxVersion = SimpleBrowser.isFirefox ? majorVer : 0;
        SimpleBrowser.ieVersion = SimpleBrowser.isIE ? majorVer : 0;
        SimpleBrowser.operaVersion = SimpleBrowser.isOpera ? majorVer : 0;
        SimpleBrowser.safariVersion = SimpleBrowser.isSafari ? majorVer : 0;
        SimpleBrowser.webKitVersion = SimpleBrowser.isWebKit ? majorVer : 0;

        this.setFlag(browserName + majorVer, true, publish); // Ext.isIE10
        this.setFlag(browserName + browserVersion.getShortVersion());
    }

    for (i in browserNames) {
        if (browserNames.hasOwnProperty(i)) {
            name = browserNames[i];

            this.setFlag(name, browserName === name);
        }
    }

    this.setFlag(name);

    if (engineVersion) {
        this.setFlag(engineName + (engineVersion.getMajor() || ''));
        this.setFlag(engineName + engineVersion.getShortVersion());
    }

    for (i in engineNames) {
        if (engineNames.hasOwnProperty(i)) {
            name = engineNames[i];
            this.setFlag(name, engineName === name, publish);
        }
    }

    this.setFlag('Standalone', !!navigator.standalone);
    this.setFlag('Ripple', !!document.getElementById("tinyhippos-injected") && !SimpleBrowser.isEmpty(window.top.ripple));
    this.setFlag('WebWorks', !!window.blackberry);

    if (typeof window.PhoneGap != 'undefined' || typeof window.Cordova != 'undefined' || typeof window.cordova != 'undefined') {
        isWebView = true;
        this.setFlag('PhoneGap');
        this.setFlag('Cordova');
    }
    else if (!!window.isNK) {
        isWebView = true;
    }
    if (/(Glass)/i.test(userAgent)) {
        this.setFlag('GoogleGlass');
    }
    if (/(iPhone|iPod|iPad).*AppleWebKit(?!.*Safari)(?!.*FBAN)/i.test(userAgent)) {
        isWebView = true;
    }
    this.setFlag('WebView', isWebView);
    this.isStrict = SimpleBrowser.isStrict = document.compatMode == "CSS1Compat";
    this.isSecure = SimpleBrowser.isSecure;
    this.identity = browserName + majorVer + (this.isStrict ? 'Strict' : 'Quirks');
};

SimpleBrowser.env.Browser.prototype = {
    constructor: SimpleBrowser.env.Browser,
    browserNames: {
        ie: 'IE',
        firefox: 'Firefox',
        safari: 'Safari',
        chrome: 'Chrome',
        opera: 'Opera',
        dolfin: 'Dolfin',
        webosbrowser: 'webOSBrowser',
        chromeMobile: 'ChromeMobile',
        chromeiOS: 'ChromeiOS',
        silk: 'Silk',
        other: 'Other'
    },
    engineNames: {
        webkit: 'WebKit',
        gecko: 'Gecko',
        presto: 'Presto',
        trident: 'Trident',
        other: 'Other'
    },
    enginePrefixes: {
        webkit: 'AppleWebKit/',
        gecko: 'Gecko/',
        presto: 'Presto/',
        trident: 'Trident/'
    },
    browserPrefixes: {
        ie: 'MSIE ',
        firefox: 'Firefox/',
        chrome: 'Chrome/',
        safari: 'Version/',
        opera: 'OPR/',
        dolfin: 'Dolfin/',
        webosbrowser: 'wOSBrowser/',
        chromeMobile: 'CrMo/',
        chromeiOS: 'CriOS/',
        silk: 'Silk/'
    },

    styleDashPrefixes: {
        WebKit: '-webkit-',
        Gecko: '-moz-',
        Trident: '-ms-',
        Presto: '-o-',
        Other: ''
    },

    stylePrefixes: {
        WebKit: 'Webkit',
        Gecko: 'Moz',
        Trident: 'ms',
        Presto: 'O',
        Other: ''
    },

    propertyPrefixes: {
        WebKit: 'webkit',
        Gecko: 'moz',
        Trident: 'ms',
        Presto: 'o',
        Other: ''
    },

    is: function (name) {
        return !!this.is[name];
    },
    name: null,
    version: null,
    engineName: null,
    engineVersion: null,
    setFlag: function(name, value, publish) {
        if (typeof value == 'undefined') {
            value = true;
        }
        this.is[name] = value;
        this.is[name.toLowerCase()] = value;
        if (publish) {
        	SimpleBrowser['is' + name] = value;
        }

        return this;
    },
    getStyleDashPrefix: function() {
        return this.styleDashPrefixes[this.engineName];
    },
    getStylePrefix: function() {
        return this.stylePrefixes[this.engineName];
    },
    getVendorProperyName: function(name) {
        var prefix = this.propertyPrefixes[this.engineName];
        if (prefix.length > 0) {
            return prefix + SimpleBrowser.String.capitalize(name);
        }
        return name;
    },
    getPreferredTranslationMethod: function(config) {
        if (typeof config == 'object' && 'translationMethod' in config && config.translationMethod !== 'auto') {
            return config.translationMethod;
        } else {
            return 'csstransform';
        }
    }

};

(function (userAgent) {
    SimpleBrowser.browser = new SimpleBrowser.env.Browser(userAgent, true);
    SimpleBrowser.userAgent = userAgent.toLowerCase();
    SimpleBrowser.SSL_SECURE_URL = SimpleBrowser.isSecure && SimpleBrowser.isIE ? 'javascript:\'\'' : 'about:blank'
}(SimpleBrowser.global.navigator.userAgent));