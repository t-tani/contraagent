var e=Object.defineProperty,t=(t,n)=>{let r={};for(var i in t)e(r,i,{get:t[i],enumerable:!0});return n||e(r,Symbol.toStringTag,{value:`Module`}),r},n=[`contraagent-dark`,`contraagent-light`,`github-dark`,`github-light`,`one-dark`,`nord`,`high-contrast`],r=[`contraagent-dark`,`contraagent-light`,`system`,`github-dark`,`github-light`,`one-dark`,`nord`,`high-contrast`],i=[`github-dark`,`github-light`,`one-dark`,`nord`,`high-contrast`],a=`contraagent-dark`,o={dark:`contraagent-dark`,light:`contraagent-light`},s={"contraagent-dark":{label:`contraagent Dark`,scheme:`dark`,tokens:{backdrop:`radial-gradient(1100px 520px at 8% -12%, #10203a 0%, transparent 62%), radial-gradient(900px 480px at 108% 4%, #1b1238 0%, transparent 58%), #060a11`,bg:`#060a11`,card:`#0f1724`,panel:`#0f1724`,panel2:`#142034`,raise:`#1a2740`,well:`#0a111c`,track:`#1b273b`,line:`#1d2940`,line2:`#2b3c58`,shadow:`#060a11`,text:`#e7edf5`,"text-2":`#bcc7d6`,"text-muted":`#909db2`,accent:`#7aa2ff`,focus:`#7aa2ff`,"focus-width":`2px`,selection:`#7aa2ff4d`,"status-failed":`#f87171`,"status-attention":`#fbbf24`,"status-done":`#34d399`,"status-running":`#22d3ee`,"status-muted":`#94a3b8`,tint:`13%`,agent:`#b597fb`,meter:`#7d8ba3`,"tok-input":`#7c86f5`,"tok-cache-read":`#3f4d63`,"tok-cache-write":`#8796ad`,"tok-output":`#d6b8ff`,"code-keyword":`#c4a5ff`,"code-string":`#7ee2a8`,"code-number":`#f5c26b`,"code-constant":`#ff9e64`,"code-comment":`#74839a`,"code-function":`#7dd3fc`,"code-type":`#ffd479`,"code-name":`#79b8ff`}},"contraagent-light":{label:`contraagent Light`,scheme:`light`,tokens:{backdrop:`radial-gradient(1100px 520px at 8% -12%, #dde7fb 0%, transparent 62%), radial-gradient(900px 480px at 108% 4%, #ebe3fa 0%, transparent 58%), #eef2f8`,bg:`#eef2f8`,card:`#ffffff`,panel:`#ffffff`,panel2:`#f7f9fc`,raise:`#e6ecf5`,well:`#f3f6fa`,track:`#e1e7f0`,line:`#d6dde8`,line2:`#b6c2d3`,shadow:`#0f172438`,text:`#0f1724`,"text-2":`#34415a`,"text-muted":`#556279`,accent:`#2f58d4`,focus:`#2f58d4`,"focus-width":`2px`,selection:`#2f58d42e`,"status-failed":`#b8132d`,"status-attention":`#6c4801`,"status-done":`#026b49`,"status-running":`#01525f`,"status-muted":`#56637a`,tint:`11%`,agent:`#6f45c0`,meter:`#8a97ab`,"tok-input":`#4d4cc8`,"tok-cache-read":`#cdd6e3`,"tok-cache-write":`#7d8aa0`,"tok-output":`#a07ad9`,"code-keyword":`#6f49a8`,"code-string":`#076b40`,"code-number":`#7b5605`,"code-constant":`#964605`,"code-comment":`#5d6b80`,"code-function":`#086586`,"code-type":`#785902`,"code-name":`#095ea8`}},"github-dark":{label:`GitHub Dark`,scheme:`dark`,tokens:{backdrop:`#010409`,bg:`#010409`,card:`#0d1117`,panel:`#0d1117`,panel2:`#151b23`,raise:`#212830`,well:`#010409`,track:`#262c36`,line:`#262c36`,line2:`#3d444d`,shadow:`#010409`,text:`#f0f6fc`,"text-2":`#d1d7e0`,"text-muted":`#9299a2`,accent:`#4796fb`,focus:`#1f6feb`,"focus-width":`2px`,selection:`#388bfd4d`,"status-failed":`#fc554d`,"status-attention":`#d29922`,"status-done":`#3fb950`,"status-running":`#39c5cf`,"status-muted":`#9198a1`,tint:`15%`,agent:`#ab7df8`,meter:`#656c76`,"tok-input":`#58a6ff`,"tok-cache-read":`#2f3742`,"tok-cache-write":`#656c76`,"tok-output":`#d2a8ff`,"code-keyword":`#ff7b72`,"code-string":`#a5d6ff`,"code-number":`#79c0ff`,"code-constant":`#79c0ff`,"code-comment":`#9198a1`,"code-function":`#d2a8ff`,"code-type":`#ffa657`,"code-name":`#7ee787`}},"github-light":{label:`GitHub Light`,scheme:`light`,tokens:{backdrop:`#f6f8fa`,bg:`#f6f8fa`,card:`#ffffff`,panel:`#ffffff`,panel2:`#ffffff`,raise:`#eff2f5`,well:`#f6f8fa`,track:`#e6eaef`,line:`#d1d9e0`,line2:`#b7c0ca`,shadow:`#1f232833`,text:`#1f2328`,"text-2":`#393f46`,"text-muted":`#59636e`,accent:`#0165d6`,focus:`#0165d6`,"focus-width":`2px`,selection:`#0969da33`,"status-failed":`#cd1e2b`,"status-attention":`#916103`,"status-done":`#147b33`,"status-running":`#10767d`,"status-muted":`#59636e`,tint:`8%`,agent:`#804ddc`,meter:`#818b98`,"tok-input":`#54aeff`,"tok-cache-read":`#d1d9e0`,"tok-cache-write":`#818b98`,"tok-output":`#a475f9`,"code-keyword":`#cf222e`,"code-string":`#0a3069`,"code-number":`#0550ae`,"code-constant":`#0550ae`,"code-comment":`#59636e`,"code-function":`#6639ba`,"code-type":`#953800`,"code-name":`#116329`}},"one-dark":{label:`One Dark`,scheme:`dark`,tokens:{backdrop:`#21252b`,bg:`#21252b`,card:`#282c34`,panel:`#282c34`,panel2:`#2c313a`,raise:`#2c313a`,well:`#21252b`,track:`#3a3f4b`,line:`#181a1f`,line2:`#4b5263`,shadow:`#0e1013`,text:`#d7dae0`,"text-2":`#abb2bf`,"text-muted":`#a7afbe`,accent:`#64b2f2`,focus:`#528bff`,"focus-width":`2px`,selection:`#3e4451`,"status-failed":`#fc858d`,"status-attention":`#e5c07b`,"status-done":`#98c379`,"status-running":`#57b7c3`,"status-muted":`#a7afbe`,tint:`12%`,agent:`#d788ee`,meter:`#5c6370`,"tok-input":`#61afef`,"tok-cache-read":`#3e4451`,"tok-cache-write":`#5c6370`,"tok-output":`#c678dd`,"code-keyword":`#c678dd`,"code-string":`#98c379`,"code-number":`#d19a66`,"code-constant":`#d19a66`,"code-comment":`#8f949e`,"code-function":`#61afef`,"code-type":`#e5c07b`,"code-name":`#e36e77`}},nord:{label:`Nord`,scheme:`dark`,tokens:{backdrop:`#2e3440`,bg:`#242933`,card:`#2e3440`,panel:`#2e3440`,panel2:`#323946`,raise:`#3b4252`,well:`#272c36`,track:`#3b4252`,line:`#3b4252`,line2:`#4c566a`,shadow:`#1d2129`,text:`#eceff4`,"text-2":`#d8dee9`,"text-muted":`#adbcd9`,accent:`#9dbedf`,focus:`#88c0d0`,"focus-width":`2px`,selection:`#4c566a`,"status-failed":`#fe9aa1`,"status-attention":`#ebcb8b`,"status-done":`#a5c18e`,"status-running":`#89c1d1`,"status-muted":`#adbcd9`,tint:`13%`,agent:`#d0a9c9`,meter:`#7b88a1`,"tok-input":`#5e81ac`,"tok-cache-read":`#4c566a`,"tok-cache-write":`#7b88a1`,"tok-output":`#b48ead`,"code-keyword":`#81a1c1`,"code-string":`#a3be8c`,"code-number":`#b790b0`,"code-constant":`#d38972`,"code-comment":`#8f9db8`,"code-function":`#88c0d0`,"code-type":`#8fbcbb`,"code-name":`#8fbcbb`}},"high-contrast":{label:`High contrast`,scheme:`dark`,tokens:{backdrop:`#010409`,bg:`#010409`,card:`#0a0c10`,panel:`#0a0c10`,panel2:`#0a0c10`,raise:`#1c2128`,well:`#010409`,track:`#272b33`,line:`#7a828e`,line2:`#9ea7b3`,shadow:`#000000`,text:`#ffffff`,"text-2":`#f0f3f6`,"text-muted":`#bdc4cc`,accent:`#7abbfe`,focus:`#7abbfe`,"focus-width":`3px`,selection:`#409eff66`,"status-failed":`#ffacb8`,"status-attention":`#fad209`,"status-done":`#0ef38e`,"status-running":`#62ceff`,"status-muted":`#bdc4cc`,tint:`12%`,agent:`#c299fe`,meter:`#9ea7b3`,"tok-input":`#409eff`,"tok-cache-read":`#525964`,"tok-cache-write":`#9ea7b3`,"tok-output":`#dbb7ff`,"code-keyword":`#ff9492`,"code-string":`#addcff`,"code-number":`#91cbff`,"code-constant":`#91cbff`,"code-comment":`#bdc4cc`,"code-function":`#dbb7ff`,"code-type":`#ffb757`,"code-name":`#72f088`}}},c=e=>`--ca-theme-${e}`;function l(e){return n.map(t=>{let n=s[t],r=Object.entries(n.tokens).map(([e,t])=>`${c(e)}: ${t};`);return`${e(t)} { color-scheme: ${n.scheme}; ${c(`color-scheme`)}: ${n.scheme}; ${r.join(` `)} }`}).join(`
`)}var u=[{name:`backdrop`,prop:`--ca-backdrop`,meaning:`the monitor's page, behind the panels (a colour or a gradient)`},{name:`bg`,prop:`--ca-bg`,meaning:`the page`},{name:`card`,prop:`--ca-card`,meaning:`a card or a graph node`},{name:`panel`,prop:`--ca-panel`,meaning:`a panel (bottom of its gradient)`},{name:`panel2`,prop:`--ca-panel2`,meaning:`a panel (top of its gradient), a sticky header`},{name:`raise`,prop:`--ca-raise`,meaning:`a raised surface: a neutral chip, a hovered row`},{name:`well`,prop:`--ca-well`,meaning:`a sunken surface: code, a graph's frame`},{name:`track`,prop:`--ca-track`,meaning:`the empty part of a bar`},{name:`line`,prop:`--ca-line`,meaning:`a border`},{name:`line2`,prop:`--ca-line2`,meaning:`a stronger border, a graph's edge`},{name:`shadow`,prop:`--ca-shadow`,meaning:`the colour of a shadow under a panel, a menu or a notice`},{name:`text`,prop:`--ca-text`,meaning:`text, and every number that is not a problem count`},{name:`text-2`,prop:`--ca-text-secondary`,meaning:`secondary text`},{name:`text-muted`,prop:`--ca-text-muted`,meaning:`labels, captions, units`},{name:`accent`,prop:`--ca-accent`,meaning:`links, the selected tab or item`},{name:`accent-bg`,prop:`--ca-accent-bg`,meaning:`a selected row or item`,derive:`color-mix(in srgb, var(--accent) calc(var(--tint) + 1%), transparent)`},{name:`focus`,prop:`--ca-focus`,meaning:`the focus ring`},{name:`focus-width`,prop:`--ca-focus-width`,meaning:`the width of the focus ring`},{name:`selection`,prop:`--ca-selection`,meaning:`selected text`},{name:`status-failed`,prop:`--ca-status-failed`,meaning:`failed: a task, an attempt, a check (with ✕)`},{name:`status-failed-bg`,prop:`--ca-status-failed-bg`,meaning:`the tint behind a failed pill or chip`,derive:`color-mix(in srgb, var(--status-failed) var(--tint), transparent)`},{name:`status-attention`,prop:`--ca-status-attention`,meaning:`not failed, needs a look: not started (with ◌), a limit near`},{name:`status-attention-bg`,prop:`--ca-status-attention-bg`,meaning:`the tint behind an attention pill or chip`,derive:`color-mix(in srgb, var(--status-attention) var(--tint), transparent)`},{name:`status-done`,prop:`--ca-status-done`,meaning:`done or passed: marks (✓) and small chips only`},{name:`status-done-bg`,prop:`--ca-status-done-bg`,meaning:`the tint behind a done pill or chip`,derive:`color-mix(in srgb, var(--status-done) var(--tint), transparent)`},{name:`status-running`,prop:`--ca-status-running`,meaning:`running, live`},{name:`status-running-bg`,prop:`--ca-status-running-bg`,meaning:`the tint behind a running pill or chip`,derive:`color-mix(in srgb, var(--status-running) var(--tint), transparent)`},{name:`status-muted`,prop:`--ca-status-muted`,meaning:`skipped, waiting, not run`},{name:`status-muted-bg`,prop:`--ca-status-muted-bg`,meaning:`the tint behind a muted pill or chip`,derive:`color-mix(in srgb, var(--status-muted) calc(var(--tint) - 1%), transparent)`},{name:`tint`,prop:`--ca-tint`,meaning:`how strong a tint is: the share of its colour in a status, agent or selected background`},{name:`agent`,prop:`--ca-agent`,meaning:`identity: an agent task's icon and edge`},{name:`agent-bg`,prop:`--ca-agent-bg`,meaning:`the tint behind an agent task's icon`,derive:`color-mix(in srgb, var(--agent) calc(var(--tint) + 2%), transparent)`},{name:`meter`,prop:`--ca-meter`,meaning:`a bar that measures, not judges: time, usage, progress`},{name:`tok-input`,prop:`--ca-tok-input`,meaning:`tokens: input`},{name:`tok-cache-read`,prop:`--ca-tok-cache-read`,meaning:`tokens: cache read`},{name:`tok-cache-write`,prop:`--ca-tok-cache-write`,meaning:`tokens: cache write`},{name:`tok-output`,prop:`--ca-tok-output`,meaning:`tokens: output`},{name:`code-keyword`,prop:`--ca-code-keyword`,meaning:`code: keywords`},{name:`code-string`,prop:`--ca-code-string`,meaning:`code and JSON: strings`},{name:`code-number`,prop:`--ca-code-number`,meaning:`code and JSON: numbers`},{name:`code-constant`,prop:`--ca-code-constant`,meaning:`code: constants, template placeholders`},{name:`code-comment`,prop:`--ca-code-comment`,meaning:`code: comments`},{name:`code-function`,prop:`--ca-code-function`,meaning:`code: functions, decorators`},{name:`code-type`,prop:`--ca-code-type`,meaning:`code: classes and types`},{name:`code-name`,prop:`--ca-code-name`,meaning:`code: built-ins; JSON: keys`},{name:`font-size-xs`,prop:`--ca-font-size-xs`,meaning:`type: the smallest text, a key or a tag`,derive:`10px`},{name:`font-size-sm`,prop:`--ca-font-size-sm`,meaning:`type: a chip, a pill, a caption`,derive:`11px`},{name:`font-size-md`,prop:`--ca-font-size-md`,meaning:`type: a section heading, a row of facts`,derive:`12px`},{name:`font-size-lg`,prop:`--ca-font-size-lg`,meaning:`type: the monitor's text`,derive:`13px`},{name:`font-size-xl`,prop:`--ca-font-size-xl`,meaning:`type: a title`,derive:`15px`},{name:`font-size-2xl`,prop:`--ca-font-size-2xl`,meaning:`type: a tile's number`,derive:`28px`},{name:`radius-sm`,prop:`--ca-radius-sm`,meaning:`corners: a key, a code span`,derive:`4px`},{name:`radius-md`,prop:`--ca-radius-md`,meaning:`corners: a row, a code block`,derive:`8px`},{name:`radius-lg`,prop:`--ca-radius-lg`,meaning:`corners: a panel`,derive:`12px`},{name:`radius-pill`,prop:`--ca-radius-pill`,meaning:`corners: a pill or a chip`,derive:`999px`}],d=e=>n.includes(e),f=e=>r.includes(e);function p(e,t){return e===`system`?t?o.light:o.dark:d(e)?e:a}var m=`contraagent:theme`,h=()=>{try{return globalThis.localStorage}catch{return}};function g(e=h()){try{let t=e?.getItem(m);if(f(t))return t}catch{}return a}function _(e,t=h()){try{t?.setItem(m,e)}catch{}}var v=()=>globalThis.matchMedia?.(`(prefers-color-scheme: light)`).matches??!1,y=globalThis,b=y.ShadowRoot&&(y.ShadyCSS===void 0||y.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,x=Symbol(),ee=new WeakMap,S=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==x)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(b&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=ee.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&ee.set(t,e))}return e}toString(){return this.cssText}},C=e=>new S(typeof e==`string`?e:e+``,void 0,x),w=(e,...t)=>new S(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,x),te=(e,t)=>{if(b)e.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let n of t){let t=document.createElement(`style`),r=y.litNonce;r!==void 0&&t.setAttribute(`nonce`,r),t.textContent=n.cssText,e.appendChild(t)}},ne=b?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return C(t)})(e):e,{is:re,defineProperty:ie,getOwnPropertyDescriptor:ae,getOwnPropertyNames:oe,getOwnPropertySymbols:se,getPrototypeOf:T}=Object,E=globalThis,ce=E.trustedTypes,le=ce?ce.emptyScript:``,ue=E.reactiveElementPolyfillSupport,de=(e,t)=>e,fe={toAttribute(e,t){switch(t){case Boolean:e=e?le:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},pe=(e,t)=>!re(e,t),me={attribute:!0,type:String,converter:fe,reflect:!1,useDefault:!1,hasChanged:pe};Symbol.metadata??=Symbol(`metadata`),E.litPropertyMetadata??=new WeakMap;var he=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=me){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&ie(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=ae(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??me}static _$Ei(){if(this.hasOwnProperty(de(`elementProperties`)))return;let e=T(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(de(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(de(`properties`))){let e=this.properties,t=[...oe(e),...se(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(ne(e))}else e!==void 0&&t.push(ne(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return te(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?fe:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?fe:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??pe)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};he.elementStyles=[],he.shadowRootOptions={mode:`open`},he[de(`elementProperties`)]=new Map,he[de(`finalized`)]=new Map,ue?.({ReactiveElement:he}),(E.reactiveElementVersions??=[]).push(`2.1.2`);var ge=globalThis,_e=e=>e,ve=ge.trustedTypes,ye=ve?ve.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,be=`$lit$`,xe=`lit$${Math.random().toFixed(9).slice(2)}$`,Se=`?`+xe,Ce=`<${Se}>`,we=document,Te=()=>we.createComment(``),Ee=e=>e===null||typeof e!=`object`&&typeof e!=`function`,De=Array.isArray,Oe=e=>De(e)||typeof e?.[Symbol.iterator]==`function`,ke=`[ 	
\f\r]`,Ae=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,je=/-->/g,Me=/>/g,Ne=RegExp(`>|${ke}(?:([^\\s"'>=/]+)(${ke}*=${ke}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),Pe=/'/g,Fe=/"/g,Ie=/^(?:script|style|textarea|title)$/i,Le=e=>(t,...n)=>({_$litType$:e,strings:t,values:n}),D=Le(1),Re=Le(2),ze=Symbol.for(`lit-noChange`),O=Symbol.for(`lit-nothing`),Be=new WeakMap,Ve=we.createTreeWalker(we,129);function He(e,t){if(!De(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return ye===void 0?t:ye.createHTML(t)}var Ue=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=Ae;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===Ae?c[1]===`!--`?o=je:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=Ne):(Ie.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=Ne):o=Me:o===Ne?c[0]===`>`?(o=i??Ae,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?Ne:c[3]===`"`?Fe:Pe):o===Fe||o===Pe?o=Ne:o===je||o===Me?o=Ae:(o=Ne,i=void 0);let d=o===Ne&&e[t+1].startsWith(`/>`)?` `:``;a+=o===Ae?n+Ce:l>=0?(r.push(s),n.slice(0,l)+be+n.slice(l)+xe+d):n+xe+(l===-2?t:d)}return[He(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},We=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=Ue(t,n);if(this.el=e.createElement(l,r),Ve.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=Ve.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(be)){let t=u[o++],n=i.getAttribute(e).split(xe),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?Ye:r[1]===`?`?Xe:r[1]===`@`?Ze:Je}),i.removeAttribute(e)}else e.startsWith(xe)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(Ie.test(i.tagName)){let e=i.textContent.split(xe),t=e.length-1;if(t>0){i.textContent=ve?ve.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],Te()),Ve.nextNode(),c.push({type:2,index:++a});i.append(e[t],Te())}}}else if(i.nodeType===8){if(i.data===Se)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(xe,e+1))!==-1;)c.push({type:7,index:a}),e+=xe.length-1}}a++}}static createElement(e,t){let n=we.createElement(`template`);return n.innerHTML=e,n}};function Ge(e,t,n=e,r){if(t===ze)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=Ee(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=Ge(e,i._$AS(e,t.values),i,r)),t}var Ke=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??we).importNode(t,!0);Ve.currentNode=r;let i=Ve.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new qe(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new Qe(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=Ve.nextNode(),a++)}return Ve.currentNode=we,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},qe=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=O,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=Ge(this,e,t),Ee(e)?e===O||e==null||e===``?(this._$AH!==O&&this._$AR(),this._$AH=O):e!==this._$AH&&e!==ze&&this._(e):e._$litType$===void 0?e.nodeType===void 0?Oe(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==O&&Ee(this._$AH)?this._$AA.nextSibling.data=e:this.T(we.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=We.createElement(He(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new Ke(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=Be.get(e.strings);return t===void 0&&Be.set(e.strings,t=new We(e)),t}k(t){De(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(Te()),this.O(Te()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=_e(e).nextSibling;_e(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},Je=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=O,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=O}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=Ge(this,e,t,0),a=!Ee(e)||e!==this._$AH&&e!==ze,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=Ge(this,r[n+o],t,o),s===ze&&(s=this._$AH[o]),a||=!Ee(s)||s!==this._$AH[o],s===O?e=O:e!==O&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===O?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},Ye=class extends Je{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===O?void 0:e}},Xe=class extends Je{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==O)}},Ze=class extends Je{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=Ge(this,e,t,0)??O)===ze)return;let n=this._$AH,r=e===O&&n!==O||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==O&&(n===O||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Qe=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){Ge(this,e)}},$e={M:be,P:xe,A:Se,C:1,L:Ue,R:Ke,D:Oe,V:Ge,I:qe,H:Je,N:Xe,U:Ze,B:Ye,F:Qe},et=ge.litHtmlPolyfillSupport;et?.(We,qe),(ge.litHtmlVersions??=[]).push(`3.3.3`);var tt=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new qe(t.insertBefore(Te(),e),e,void 0,n??{})}return i._$AI(e),i},nt=globalThis,k=class extends he{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=tt(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return ze}};k._$litElement$=!0,k.finalized=!0,nt.litElementHydrateSupport?.({LitElement:k});var rt=nt.litElementPolyfillSupport;rt?.({LitElement:k}),(nt.litElementVersions??=[]).push(`4.2.2`);var it=C(l(e=>`[data-ca-theme="${e}"]`)),at=C(l(e=>`:host([data-ca-theme="${e}"])`)),ot=new WeakSet;function st(e=document){if(ot.has(e))return;let t=it.styleSheet;t&&`adoptedStyleSheets`in e&&(e.adoptedStyleSheets=[...e.adoptedStyleSheets,t],ot.add(e))}function A(e,t,n,{bubbles:r=!0}={}){e.dispatchEvent(new CustomEvent(t,{detail:n,bubbles:r,composed:!0}))}var ct=[`overview`,`tasks`,`journal`,`outputs`,`definitions`,`procs`,`stream`],lt=[`transcript`,`input`,`output`,`definition`],ut=e=>ct.includes(e)||/^panel:.+/.test(e),dt=e=>lt.includes(e);function ft(e){let t=new URLSearchParams(e),n=t.get(`tab`)??``,r=t.get(`view`)??``,i=Number(t.get(`round`));return{run:t.get(`run`)??``,tab:ut(n)?n:`overview`,key:t.get(`key`)||null,view:dt(r)?r:`transcript`,round:Number.isInteger(i)&&i>0?i:null,def:t.get(`def`)||null,kind:t.get(`kind`)??``,stop:t.get(`stop`)??``,q:t.get(`q`)??``,layer:t.get(`layer`)??``,unit:t.get(`unit`)??``,sel:t.get(`sel`)??``}}function pt(e){let t=new URLSearchParams;e.run&&t.set(`run`,e.run),e.tab!==`overview`&&t.set(`tab`,e.tab),e.tab===`stream`&&(e.key&&t.set(`key`,e.key),e.view!==`transcript`&&t.set(`view`,e.view),e.round!=null&&t.set(`round`,String(e.round))),e.tab===`definitions`&&e.def&&t.set(`def`,e.def),e.tab===`overview`&&e.layer&&t.set(`layer`,e.layer),e.tab===`overview`&&e.unit&&t.set(`unit`,e.unit),e.tab===`overview`&&e.sel&&t.set(`sel`,e.sel);let n=e.tab===`tasks`||e.tab===`journal`;n&&e.kind&&t.set(`kind`,e.kind),e.tab===`journal`&&e.stop&&t.set(`stop`,e.stop),n&&e.q&&t.set(`q`,e.q);let r=t.toString();return r?`?${r}`:``}function mt(e,t){let n={...e,...t};return t.run!==void 0&&t.run!==e.run&&Object.assign(n,{key:null,def:null,round:null,layer:``,unit:``,sel:``,...t}),t.layer!==void 0&&t.layer!==e.layer&&t.sel===void 0&&(n.sel=``),t.key!==void 0&&t.key!==e.key&&(t.view===void 0&&(n.view=`transcript`),t.round===void 0&&(n.round=null)),n}function ht(e,t){let n=e=>pt({...e,kind:``,stop:``,q:``,unit:``,sel:``});return n(e)!==n(t)}var gt=class{constructor(e,t,n,r=()=>{}){this.mode=e,this.onChange=t,this.onLeave=r,this.onPop=()=>{this.current=ft(location.search),this.onChange(this.current,`pop`)};let i=ft(e===`url`?location.search:``);this.current=mt(i,n??{})}get route(){return this.current}start(){this.mode===`url`&&(history.scrollRestoration=`manual`,addEventListener(`popstate`,this.onPop)),this.onChange(this.current,`init`)}stop(){this.mode===`url`&&removeEventListener(`popstate`,this.onPop)}navigate(e,t={}){let n=mt(this.current,e);if(pt(n)===pt(this.current))return;let r=!t.replace&&ht(this.current,n);if(this.current=n,this.mode===`url`){let e=`${location.pathname}${pt(n)}${location.hash}`;r?(this.onLeave(),history.pushState({},``,e)):history.replaceState(history.state,``,e)}this.onChange(n,r?`push`:`replace`)}},_t=`lit-localize-status`,j=(e,...t)=>({strTag:!0,strings:e,values:t}),vt=e=>typeof e!=`string`&&`strTag`in e,yt=(e,t,n)=>{let r=e[0];for(let i=1;i<e.length;i++)r+=t[n?n[i-1]:i-1],r+=e[i];return r},bt=(e=>vt(e)?yt(e.strings,e.values):e),M=bt,xt=!1;function St(e){if(xt)throw Error(`lit-localize can only be configured once`);M=e,xt=!0}var Ct=class{constructor(e){this.__litLocalizeEventHandler=e=>{e.detail.status===`ready`&&this.host.requestUpdate()},this.host=e}hostConnected(){window.addEventListener(_t,this.__litLocalizeEventHandler)}hostDisconnected(){window.removeEventListener(_t,this.__litLocalizeEventHandler)}},wt=e=>e.addController(new Ct(e)),N=()=>(e,t)=>(e.addInitializer(wt),e),Tt=class{constructor(){this.settled=!1,this.promise=new Promise((e,t)=>{this._resolve=e,this._reject=t})}resolve(e){this.settled=!0,this._resolve(e)}reject(e){this.settled=!0,this._reject(e)}},Et=[];for(let e=0;e<256;e++)Et[e]=(e>>4&15).toString(16)+(e&15).toString(16);function Dt(e){let t=0,n=8997,r=0,i=33826,a=0,o=40164,s=0,c=52210;for(let l=0;l<e.length;l++)n^=e.charCodeAt(l),t=n*435,r=i*435,a=o*435,s=c*435,a+=n<<8,s+=i<<8,r+=t>>>16,n=t&65535,a+=r>>>16,i=r&65535,c=s+(a>>>16)&65535,o=a&65535;return Et[c>>8]+Et[c&255]+Et[o>>8]+Et[o&255]+Et[i>>8]+Et[i&255]+Et[n>>8]+Et[n&255]}var Ot=`h`,kt=`s`;function At(e,t){return(t?Ot:kt)+Dt(typeof e==`string`?e:e.join(``))}var jt=new WeakMap,Mt=new Map;function Nt(e,t,n){if(e){let r=e[n?.id??Pt(t)];if(r){if(typeof r==`string`)return r;if(`strTag`in r)return yt(r.strings,t.values,r.values);{let e=jt.get(r);return e===void 0&&(e=r.values,jt.set(r,e)),{...r,values:e.map(e=>t.values[e])}}}}return bt(t)}function Pt(e){let t=typeof e==`string`?e:e.strings,n=Mt.get(t);return n===void 0&&(n=At(t,typeof e!=`string`&&!(`strTag`in e)),Mt.set(t,n)),n}function Ft(e){window.dispatchEvent(new CustomEvent(_t,{detail:e}))}var It=``,Lt,Rt,zt,Bt,Vt,Ht=new Tt;Ht.resolve();var Ut=0,Wt=e=>(St(((e,t)=>Nt(Vt,e,t))),It=Rt=e.sourceLocale,zt=new Set(e.targetLocales),zt.add(e.sourceLocale),Bt=e.loadLocale,{getLocale:Gt,setLocale:Kt}),Gt=()=>It,Kt=e=>{if(e===(Lt??It))return Ht.promise;if(!zt||!Bt)throw Error(`Internal error`);if(!zt.has(e))throw Error(`Invalid locale code`);Ut++;let t=Ut;return Lt=e,Ht.settled&&(Ht=new Tt),Ft({status:`loading`,loadingLocale:e}),(e===Rt?Promise.resolve({templates:void 0}):Bt(e)).then(n=>{Ut===t&&(It=e,Lt=void 0,Vt=n.templates,Ft({status:`ready`,readyLocale:e}),Ht.resolve())},n=>{Ut===t&&(Ft({status:`error`,errorLocale:e,errorMessage:n.toString()}),Ht.reject(n))}),Ht.promise},qt=`en`,Jt=[`ja`],Yt=[`en`,`ja`],Xt=t({templates:()=>Zt}),Zt={"definition-output":`出力`,h5665d16ae525ca0b:D`${0} の出力`,h612ee972e5585763:D`JSON オブジェクト（スキーマ ${0}）`,h876bf17c2237f30a:D`依存先タスク ${0}`,h8e239826489c9dd4:D`この実行には階層 <code>${0}</code> がありません`,had57861b5eb1998e:D`ファイルなし | Python コードで定義（<code>TaskAdapter</code>）`,hca6c01d40814d5b0:D`実行中 ${0}${1}`,hf139a496c0f9b763:D`${0} の出力から`,"no-runs-yet":`実行はまだありません`,none:`なし`,"outcome-done":`完了`,s02044ab83f193b3b:`レート制限、エラー、タイムアウトなどで失敗した後の、次のモデルへの切り替え（Router のホップ）`,s030b3188c7fcf26d:j`カスタムビュー ${0} はありません`,s0379fc73608ab971:`完了`,s0382d73823585617:j`${0}: ${1}`,s038b2a0deba58916:`ページ`,s03b454fb08e876ad:`タブ`,s03ee3cfb0919c62c:`タスク`,s03fb84d070eb4d43:j`古い試行 ${0} 件は非表示`,s051e95917479e3a4:`実行中のエージェントのセッション`,s05548eaadd7b3e53:`選択中の項目`,s061a40d8b1403d96:`OutputContract`,s0622a6e6cb77254b:`トランスクリプト`,s0668067982f84dcb:`ユニットごとのステージとステップ（CursorStore）`,s066d70cf9d5e2915:`出力`,s06a59d9f860b0c38:`Esc: 1 つ上の階層`,s06ac9901d5ec124e:`依存先`,s06bab80ab006c3bc:`エージェントのセッション開始時に報告された値です。アカウント全体の値で、同時に実行中のタスクすべてに共通です。`,s07760df6abc2f6a0:`テキストフィルター（/）`,s0799e2b0ce300ca7:j`キャッシュ ${0}`,s07da69ddbc0d4c69:`関数`,s07e46807b4a9183c:j`+${0}`,s087d6f07b52b30ec:j`${0}%`,s08b35907b5589afa:`いいえ`,s09323b2ac0a8afed:`出力の検証: OK`,s09bb59cd137c1af4:`プロンプトなし`,s0b237aba4a56eb22:`エージェントのセッション開始時のサブスクリプション利用率（アカウント全体）`,s0b355fde970b0df9:`OK`,s0b7f9dcca2fb294a:`実行前からあるファイル`,s0cf77430f4bd7c5c:j`モデル切り替えのあったタスク ${0} 件`,s0d7aa7237dcb1b28:j`キャッシュ書き込み ${0}`,s0dbd76eb398aa733:`未実行（入力ファイルの不足または検証エラー）`,s0e6bbd9fe1101fbd:`問題`,s0ea064cda0585ae9:`プラグインディレクトリ`,s0f04e0aca045fbe9:`一部省略`,s0f136ff2c086b760:`リセット済み`,s0f8b4a05ed3a104d:j`出力ファイル ${0} 件`,s10337c73438593bc:`再開カーソル`,s1072ae09dfd51f53:`種別の最初のタスクの開始時に記録（definitions/&lt;kind&gt;.json）`,s1147e23008e266b7:j`${0} 型の JSON 値`,s115763f2236ae9b6:`過去 24 時間`,s1198336b172c6e1a:`モデル切り替えのあったタスク 1 件`,s123b7254b44dd148:`待機中`,s125a86b2f45bbb25:j`要素 ${0} 個`,s12c35dcdc5890192:`型の不一致`,s14bd607323778cb3:`コーディングエージェントが報告した値`,s150f53f8651b4384:`出力`,s156d30b96fb26c7f:`なし（任意）`,s158eba9bc2227ce3:j`週の利用率 ${0}`,s1633e83dc53b5d08:`検証対象のファイルなし`,s168ae294e3e72ce4:`検証のタイミング`,s1703f5cfa8ed0cc9:j`実行されず ${0} 件`,s179ba9809bdf35c7:`アカウントごと、最初の値 → 最後の値`,s17ee023c53dcd83c:`書き込み待ち（タスクが待機中）`,s18d4d02c2e47cf0f:j`ループ内の ${0}`,s19ed92a422ad7e4c:`上限: max_concurrent`,s1a20210c3f1e40c9:j`スキップ ${0} 件`,s1a3bf4da26280428:`種別 · ユニット`,s1ac8c23d19212c8a:`エディタのテーマ`,s1acc85c236fed879:`書き込まれていない出力 1 件（タスクが未実行）`,s1b5c88ed6d70d50e:j`タスクは ${0} 回目で完了`,s1bb7c4234aa7d213:`すべてのタスクが開始済み`,s1bf54dcd1c885a20:`実行中のプロセスなし`,s1c0f7e3a9a6bce79:`パラメータ`,s1c2af4de03b03b48:`タスクが選択されていません`,s1c4244f27dc0a0ad:j`セッション開始時の利用率（アカウント全体）: ${0}`,s1c76dcdfd0d3326d:`実行に登録されたすべてのタスク（種別ごと、plan.jsonl）`,s1cc744978f1e1e36:`実行中の Python タスク`,s1db2936d905dfc71:`API エラー`,s1dc338639fe7aae9:j`試行 ${0} 回`,s1dd7ab260efc97bf:`実行中のタスクなし`,s1e9a9d076c64051d:j`プロンプト（${0} 文字、ほか ${1} 文字は未保存）`,s1ebbae8f5810b65b:`入力`,s1f53dce0721a5fdc:j`所要時間 ${0}`,s2073c04640f9ffe1:`修正依頼: 検証エラー後の、同じエージェントのセッション`,s20e04bdc808a6442:j`リセットまで ${0}`,s217ae8afd4252eff:`あり`,s2216c1ec1d2b68a8:`JSON ではありません`,s224181db56bd4f90:`ツール実行中に中止`,s229e98b8f3010c9f:j`修正依頼 ${0} 回で完了。最初の検証エラー: ${1}`,s22d4df747c023383:j`修正依頼 1 回で完了。最初の検証エラー: ${0}`,s23005b43f30a04ed:`スキーマにないフィールド`,s234af65b52814aa0:`終了した試行はまだありません`,s236ae937cbcd6a39:`拡大`,s23ba00b0f333e17e:j`${0} 回の試行がすべて失敗: ${1}`,s23f40d3ffdd352a6:`定義はまだありません`,s2575361362fcf642:`OutputContract・InputContract を宣言したタスクはありません`,s26012de2ae38a284:`API 呼び出し 1 回`,s26bae2d058ab07f8:`ユニットなし`,s26bb7d0992115fe1:`実行した試行の回数（リトライを含む、journal.jsonl）`,s26e1e2905dce8250:j`API 呼び出し ${0} 回`,s27bbde3f68fad181:j`ユニット: ${0}`,s28f91da403800c05:`InputContract`,s2a2e8a5afcc8d89a:`現在`,s2ac18b95949a85cb:j`${0}: ${1}、次のモデルに切り替え`,s2b82c03a0f482d56:`入力ファイルの不足または検証エラー`,s2cf203a7f1d1b7cb:`修正依頼: 出力が検証エラーになった後の、同じエージェントのセッションでの次のラウンド`,s2dd7dfcce562730a:`試行の結果（stop）`,s2e3f7c747d87ba60:j`ほかの出力 ${0} 件`,s2e422519ed38f7d8:`周`,s2ec303c39937657c:`タスクは実行中`,s2f3435308f48080e:j`${0} 周`,s2f3c9db4daa3e192:`問題なし`,s2f4e0fd086ad4b96:`すべての出力`,s2f54740b39931f87:`定義なし`,s2faec8a0d7db08dd:j`5 時間枠の利用率 ${0}（リセット ${1}）`,s2fe3f0ef38a252c7:`ツール`,s2fea0e9e542e5b47:j`修正依頼 ${0}`,s321b04e2b2f863d5:`余分なフィールド`,s326385425f7ff3c5:j`キャッシュ読み込み ${0}`,s33b572e03cbb49a2:`パイプラインの階層`,s343dead26eec35c9:`新しいイベント 1 件を表示`,s34970ae2312009f5:`エラーの内容は修正依頼のプロンプトに記載`,s351d1cb40ce52b1e:`終了した試行なし`,s352069454f38346a:`ファイル全体`,s355f4ca5b99c3871:`入力ファイルに検証エラー`,s367d079d1aed1358:`料金`,s36eb49cc97df66bc:j`所要時間 ${0}`,s3700ce266079b566:`Web 検索 1 回`,s370bd0b51ee4fda0:j`報告時刻 ${0}`,s37da018e1fe6a0d7:`スキーマ以外の検証（validators）`,s387a4a41718122cb:j`検索結果 ${0} 件`,s3904df152788b23c:`JSON オブジェクトではありません`,s39ee2f1fc48e6bc3:`パイプライン`,s3aa67b8233b5ecd0:`出力ファイルなし`,s3afd657caafb54ce:`上段は入力 / 出力トークン、下段はキャッシュ読み込み / キャッシュ書き込み`,s3b32dd23d086c992:`プロセスツリー`,s3bde79a5267baa21:j`task_detail コールバックが失敗: ${0}`,s3c6c1ae328e812d5:`実行した試行の回数`,s3cd8af104999d502:`実行中のエージェントのセッション 1 件`,s3d03990e188bfbff:`エージェントのセッション`,s3d197283cb019b5a:`概要`,s3d99e317c3b7b422:`検証エラー後の、同じエージェントのセッション`,s3d9b2f1277134dfc:`テキストファイル`,s3f18b1a78ce1a960:`各タスクが書き込むファイル`,s3f6e4868742b58de:j`${0} 回目で完了（失敗 ${1} 回）。最初の失敗: ${2}`,s3f7074a6bbbd7726:`修正依頼`,s3fd6bd99e3f6a5be:`開始`,s40750d44c5ea3271:j`${0}: 入力`,s4085b471de2e2215:`週の利用率`,s4134711b0b981089:`Tab: 次のノード`,s4156c144093d2565:`修正依頼が 1 回以上あった試行`,s423b98420bc4f51a:j`${0} 回目で完了（失敗 1 回）。最初の失敗: ${1}`,s42a1ebe17efda727:`フィールド`,s42c16f17debe21c7:j`${0} ステップ完了`,s42cbd8dca939a9c7:`検証`,s43809cc80b3f099a:`ハイライトを解除`,s43ab3e3c4dea42fc:`入力ファイル`,s448ad430047b3ff5:`ファイルの検証: OK`,s451bb7dd42aaf221:`料金の高いタスク`,s454c0dcbb0dffc2f:j`${0} のループの各周`,s45de7528c20a0792:j`${0}（カスタムビュー）`,s467ceab5071e77a3:j`1 周: ${0}`,s46f1d86ffec6223c:`エラーで終了`,s473bad4c26a1a663:`キャッシュ読み込み`,s478b912874fef59f:`検証対象のファイル（OutputContract、InputContract）`,s47a6fad95948980d:j`このタスクの入力 ${0} 件`,s47b9912260b01c3c:`Python タスク`,s47c42ef44972974f:`未対応のイベント`,s48287bbcb6ba7b8d:j`終了 ${0}`,s48e186fb300e5464:`所要時間`,s49098dfd8a30a9b7:`モニターのサーバーに接続済み`,s491765412b82838e:j`${0} のループ`,s4abcddbf0c24a4e2:j`${0} 日前`,s4d613d768e2faa0d:`検索結果 1 件`,s4d890c06c9c42dee:`モデル切り替え`,s4efee5b48a4593cb:`ループ`,s4f0af1e75e3f4e0d:`スキーマにない`,s4fed3c544c5791df:`エージェントタスク`,s500fd71a4232050e:`空`,s521a16a18cfbcf5a:`1 ユニット`,s52c75c50315f2111:`次の周`,s52cfd5bdf53cbac3:`カスタムビュー`,s53c57cf5a0992de1:j`${0}: 未実行`,s54393bfa280ea55b:`プロンプト`,s552240946fb80e49:j`フロー呼び出し ${0}`,s5552cf25dfb16715:`プラグインディレクトリ`,s558d71789938dd8d:`認証情報の不一致`,s55fa598b754cc3cc:j`${0}（${1}）`,s5667ab3a2fddedf6:j`（ほか ${0} 文字は未保存）`,s56838581fa8422a5:j`後続タスク: ${0}`,s571b714236b36ed9:j`入力 ${0} がありません（${1} が未実行）`,s57402fcb8174003c:j`キャッシュ書き込み ${0}`,s585632ad63b34266:j`入力 ${0} がありません（${1} が失敗）`,s58c754018ec47b5f:`実行履歴`,s594159521842aa08:j`修正依頼 ${0} 回`,s59e4f00624df1f3f:`上限に接近`,s5ab755785f15d57e:`並び順`,s5b2aca393ddc3642:`修正依頼のあったタスク 1 件`,s5b91c14a6a040e1e:`種別ごとのトークンと料金`,s5cd51fca94ab558d:j`エージェントのセッション ${0} 回`,s5de9d2dc62f214f9:`依存先タスク`,s5e30a7b87ccdc74f:`書き込みなし（タスクが未実行）`,s5e6c4b6767bd9690:`テキスト（JSON 文字列）`,s5f22ded7520dee36:`ロールなし`,s5f31efe25292c85d:`エージェント・モデル・認証情報`,s5f343a43e7ea9f91:`エラー`,s5f43af3669b1e098:`ソース`,s5f7e595afb1d20c1:`なし（必須）`,s5ff154de087b8fbf:`エージェントタスク`,s60147fb4fa4a8e0c:`実行中`,s605757aea05668c5:j`未実行の後続タスク ${0} 件`,s62035be5de828c62:`キャッシュ書き込み`,s629576c6b305d539:`任意`,s630a7291de06d7e3:`実行履歴の未実行のタスク`,s6338c9c6cf8d4720:`入力・出力トークン（全試行）`,s649816288746372b:`後続タスク`,s65ca38fd016064d1:`中断`,s6645c79330d551d1:`拡大（Ctrl + スクロール）`,s6647f4305129ff48:`ファイルなし`,s664bf0dfe5ccdd70:`ツール呼び出しが戻る前に実行が終了`,s670ef751f29dc9ae:j`${0} ユニット`,s680fc90489553ed6:`タイムライン`,s68818ff23f9c3cd6:`その他の検証`,s69522c8fd29e217c:`修正依頼 1 回`,s69990579b19fd554:j`スキーマ ${0}`,s6a8fac496ab75484:j`入力 ${0} がありません（${1} が未完了）`,s6aabc9569e449784:`未実行（入力ファイルなし）`,s6b8a04c7fc4c0cfd:j`同時実行 ${0}/${1}`,s6b94519d3d694140:`タスクなし`,s6c306ba2a3eafe04:`依存先タスクなし`,s6c80deca380c99b3:`タスクなし`,s6c86e2a18e78587f:j`依存先タスク ${0} が失敗`,s6d739294ba8eba32:j`${1} タスク中 ${0} 件完了`,s6dbe9cb1faacdff3:j`${0} 文字`,s6ebc9bd6feae62a3:`読み込み中…`,s6f145ecab7e01aae:`API 呼び出し`,s6f2d39e45dc290b5:`出力ファイル 1 件`,s6f6ef83186f41f9c:`すべてのエージェントのセッションの合計（同時実行の分も含む）`,s6fa4fa0db6637ca7:`フロー呼び出しがエラーで終了`,s706837052444dc71:`実行グループ`,s7081cf6429d6e736:j`ループ ${0} 周目`,s70a75a654c87e121:j`タスク終了後の利用率: ${0}`,s70af97de3ad8fb23:`種別`,s71900089efd0b3f6:j`モデル切り替え: ${0}`,s7233e6b5b69a2313:`古い試行 1 件は非表示`,s7239ff29fb5724bc:j`修正依頼のあったタスク ${0} 件`,s72dc3c241ce33d1c:`ユニットごとの周回数`,s72dd85d5a32d1dc3:`キャッシュ読み込み`,s737a2225351a2d83:`ループの周回数`,s73d2ca96ea1a1a1f:`未実行の後続タスク 1 件`,s755ec54babc00670:j`プラグイン ${0}`,s75834d577f713a10:`エージェントのセッションなし`,s75ee52426b34dd6d:`実行を検索`,s7671567ef7075153:j`${0} モニター`,s769a35c122b0add4:j`${0}: ${1}、${2} に切り替え`,s77ec32fb8248c021:j`未実行 ${0} 件`,s78fd8c03f8c967f3:`トークン`,s79a4abd140c07a19:j`未対応のイベント: ${0}`,s79faeb77f29174c8:j`5 時間枠の利用率 ${0}`,s7a14301773287a5c:`エラーで終了したフロー呼び出し 1 件`,s7a30a0774744040b:`出力ファイル`,s7a4c9d94aaf75c45:`権限エラー`,s7ae683e966f797d8:`タスクは待機中`,s7b16665b242b03f9:`入力ファイルなし`,s7b1cef9707986270:`修正依頼のあった試行`,s7c08c2107990421e:j`${0} を表示`,s7c95876637f6a9d7:`フィルター`,s7ccddac9af610a9c:j`${0} 回目で完了（失敗 1 回）`,s7cd807ec1a76a454:`このタスクの入力 1 件`,s7cfd548e0b7e3ad7:`出力が止まった`,s7e796fe83982863f:j`ロール ${0}`,s7f59f507e02a2f38:`表示形式`,s7ff1975047cd672c:`コーディングエージェントが使ったモデル`,s803ce7e1a2294d50:`ファイル`,s8162d2730a5efc31:`モデル切り替えなし`,s81784b8f13a711a6:`モデル切り替え: 次のモデルでの新しいエージェントのセッション`,s81816ae715e0080c:`入力ファイルの不足または検証エラーで、タスクは未実行`,s822f38a61c9dbabc:j`以前の試行のモデル: ${0}`,s837f3597be0e0bda:j`書き込み ${0}`,s83a117a0e5a969a7:`1 ステップ完了`,s84126fa92f00b4ef:`たった今`,s843c1705315bbf4e:j`修正依頼 ${0} 回後`,s84fb675fb17d4455:`リトライ`,s851220394bf4ca62:j`テーマ: ${0}`,s851d0f73d02cf0b5:`ファイルの値`,s85994a70cd39166c:`実行中`,s85e6ce57abc3c81c:j`${0}: モデル切り替え`,s863c685c886dd083:j`入力 ${0} がありません`,s864c948d4629240f:`全体を表示`,s877a8bf58317ec9e:j`${0} 回目の失敗後の、新しいエージェントのセッション`,s87aaf1391fb727b7:`実行されず`,s87b0c0d87ec9c3a1:j`モデル切り替え後に完了: ${0}`,s87cfcf0fecad5ace:`修正依頼 1 回後`,s888d98a196a240d8:`入力`,s88e6f151026426e7:j`修正依頼 ${0}`,s892f20ba2aadea33:j`入力 ${0}（${1} の出力）がありません`,s89ece7813063852e:`パラメータなし`,s8a56a8c8bd19c9c7:`なし`,s8a59bcc106a68c08:j`PID ${0}`,s8ab194afc8c3ff86:`コーディングエージェント`,s8ad90bcc234667ee:`周回数`,s8b14867a2824dc66:`リトライしたタスク`,s8bbe7f1c618318b1:`終了したすべての試行から集計（journal.jsonl）`,s8c1837e74a81ad0d:j`${0} 分前`,s8d4bb019f3bc7202:`PID`,s8dd1924ee42c1f45:j`キャッシュ読み込み ${0}`,s8de4c61438ac59f8:`再開後の実行での、新しいエージェントのセッション`,s8dfeaf9950df0ffa:`オブジェクト`,s8e337d18c39babc7:`アシスタント`,s8e609688324130a6:`Python コードで定義`,s8e92b07ba776ed4a:j`ほか ${0} アカウント`,s8eaa2ebab2c57d9f:`Tab: 次の行`,s8eec5711640b68b9:j`コーディングエージェントのイベント種別のうち、このバージョンの contraagent が対応していないもの: ${0}`,s8f18916860db5d80:`選択を解除`,s8f26e0f086cc2787:`ユニット`,s8f5f41272268128f:`未実行`,s90f3ce6dfe4ed0ce:`認証エラー`,s9147091d090a92d4:j`最大 ${0} 周`,s919d209719302bd3:j`${0}d ${1}h`,s9246c889a0392130:j`モデル ${0}`,s92a32f8361a3a3b0:j`依存先タスク ${0} 件の出力待ち`,s92b7e489ad4779c7:j`5 時間枠 ${0}`,s9340e2a9e1808cbd:`試行 1 回`,s947887a004e02e33:j`作成元: ${0}`,s94d63573d312fe9b:`認証情報`,s94f08f46277af7d6:`実行中のタスク`,s95f6abd3bc028e9c:j`依存先: ${0}`,s967a2db7049dc90e:j`失敗 ${0} 件`,s96ad55844e8c85d9:`コンテキストの上限`,s96cd46414e7cb3ee:j`出力 ${0}`,s9709015aaaed72e8:`実行中ではありません`,s97c3c9984ad4bbbc:j`修正依頼 ${0} 回で完了`,s980dd0446ac478b4:`テキストフィルター`,s98fc8cf0000154d3:`入力ファイルなし`,s9a23fee499e1a22d:`すべてのプロセス`,s9a44f95f7acf28e0:j`失敗: ${0}`,s9a629cca97d7a771:j`Web 検索 ${0} 回`,s9b1a610c6b10af9d:`実行中ではありません`,s9b7d6466c580aa00:`書き込みなし（タスクが失敗）`,s9cb681a778c29f1b:`内部の表示あり`,s9d60d7651126c205:`最終応答なしで終了`,s9de543933e6e703a:`モデル`,s9e06cbf9c5f57859:j`状態: ${0}`,s9e8afbe69b10d822:`未実行（入力ファイルに検証エラー）`,s9f0023dbc7b35c31:j`入力 ${0}`,s9f7452dd75d54d31:`エラー`,s9f92162e244d030b:j`${0} の内部`,s9f979c9a653c5aa5:`料金の上限`,s9fbbc819fe7e66aa:`実行`,s9fd13600c5948a5d:`タスクの開始前からあるファイルも有効`,s9ff6bfdb36b47dd6:`モデル切り替え`,sa0a6e71350fd953b:`出力を待つ`,sa12ff035c78855af:`コーディングエージェントが認証に使ったアカウントまたは API キー（credential）`,sa23567d1be73e6a7:`ターン数の上限`,sa335a9687e946152:`後続タスクなし`,sa358ec1ff0c833b9:`ロール`,sa35c067275510aa7:`試行`,sa390213ff60c0fd9:j`実行中のエージェントのセッションの新しいイベント ${0} 件を表示`,sa3c9339de23c1752:`形式`,sa3d3f3845c4fa2c4:j`週の利用率 ${0}（リセット ${1}）`,sa434ad4d2100f245:`作成元`,sa48318e1513f445c:`コマンドライン`,sa50a6326530d8a0d:`折りたたむ`,sa58fd816ed43f98e:`周回数`,sa6295f265bf36f55:j`${0}: トランスクリプト`,sa65ede9447b8f6f0:j`${0} 回目で完了（失敗 ${1} 回）`,sa66db52d0401c35d:j`前の ${0} 行を表示`,sa71f10bfe8f2e3b9:`期待する型`,sa74be5e915086e8e:`縮小（Ctrl + スクロール）`,sa81e2cdaf6921adc:`システム設定に合わせる`,sa84bd87e8f0df3f5:j`新しいイベント ${0} 件を表示`,sa86ea054ad5277ce:j`${0} 時間前`,sa87126e2d984d351:`ソースを表示`,sa8865b3bf47ba11f:j`${0} の入れ子のループ`,sa8bd7200899b14c8:`Shift + 矢印キー: 依存先タスク・後続タスク`,sa9ba2bef6a85be35:`タスク詳細`,saa08e9b351f629c4:`書き込み待ち（タスクが実行中）`,saa29a2ac03cd9d19:`理由`,saaaf4d8d7823ecc2:`5 時間枠の利用率`,saab875d8cfcfe712:`テーマ`,sab5bbfc5ec1101a1:j`${0} 行目`,sabd480ab5c691fa7:`思考`,sac1ead3bc64c3402:`モニターのサーバーに未接続`,sad951affb16c18e8:`API リクエストを再送`,sae5d87e99fe081e0:`必須`,sae675aed0baadfc5:`実行履歴のリトライしたタスク`,safdeae829048fe4f:j`${0} 回目が失敗: ${1}`,sb05ee36313adad06:`エラー`,sb067d7b999cdf867:`実行履歴の修正依頼のあった試行`,sb0c5ebf2450daf53:`サブスクリプションの利用率`,sb0fd4b074f0dc196:`Python タスク 1 回`,sb105a27af3c34dd9:j`未実行: ${0}`,sb1068f146c4596c3:`検索語`,sb1ffef0fea624d13:`前の 1 行を表示`,sb26a93fd31e2f700:`登録順`,sb26f6e41558f71ed:`表示中の階層の外`,sb271968591691cd3:`Enter: 開く`,sb289ca473d87fa82:`キャッシュ書き込み`,sb31160f9d54a1178:j`プロンプト（${0} 文字）`,sb45a9b8907f0b38a:`リトライしたタスク 1 件`,sb4d67c0a20dacf94:`トランスクリプトなし`,sb51d4fbebeb0e2ec:`パイプラインのプロセス内`,sb53f7a197981b790:`はい`,sb557a3a544242a40:`コーディングエージェントが報告した値`,sb5ae7a6b849639af:`未実行`,sb6bb16aa7550533d:`タスク実行中の書き込みが必須`,sb89b16909f010061:`エージェントのセッション 1 回`,sb9855c13b2b8461f:j`${0}: 完了`,sb998a18b54658de7:`トークンと料金`,sb9c8c7e97598bc93:j`Python タスク: ${0}`,sba376ab929e3896d:`1 周`,sba781480d2e52d6a:`ほかの出力 1 件`,sba8659178319945b:`検証を通るファイルを書き込む前に、タスクが失敗`,sbaf87689cccc53eb:`要素 1 個`,sbb202211084591ed:`開始時の利用率`,sbb77dd1d4c08e701:j`${1} タスク中 ${0} 件が未完了`,sbb99d4ec27fbb263:`終了`,sbc65d1b9648966de:j`${0} 周: ${1}`,sbc95529382a8202f:j`以前の試行のモデル: ${0}`,sbca0391cb2c7c054:`タスクの開始時`,sbcce076a4882d945:`依存先タスクが失敗`,sbce72abc083f229d:`失敗した試行の後の試行（毎回新しいエージェントのセッション、RetryingRunner）`,sbd4aeb401e751129:`実行を切り替え（r）`,sbd9a674a977ac3b7:`再開後`,sbe299a9270c76655:`実行履歴の失敗した試行`,sbed050affb1455dd:`全試行の合計`,sbf189e73c517d820:`種別のロール`,sbf299a5316967a33:`アクティビティなし`,sc032b109be3096a1:`それ以前`,sc15ad44c7902a717:`スキップ`,sc1ae48fd5a58a916:j`待機中 ${0} 件`,sc1b187568fa11c8c:j`リトライしたタスク ${0} 件`,sc46bcff777c978a4:`タイムアウト`,sc5751344f7cedf0f:j`入力 ${0} に検証エラー`,sc5b9f26a8c698f76:`次のモデルでの新しいエージェントのセッション`,sc61813a1424783fc:j`週 ${0}`,sc65ea2cf2f21a13a:`縮小`,sc6c0d07e39170334:j`書き込まれていない出力 ${0} 件（タスクが未実行）`,sc6fd207e5b80c46e:j`エラーで終了したフロー呼び出し ${0} 件`,sc7d1e9a9024b4f9c:`同時実行（上限）`,sc87df95c02f9306d:j`終了 ${0}`,sc92905d14a9421f3:`空き`,sca4ca1724004c913:`プロセスなし`,sca68313fa6851125:`プレビューを表示`,sca7fed2bef53cb99:`ロール`,scb862deeee160b4a:`終了（未完了のタスク 1 件）`,scb967cb2ce8bd344:`最終試行の終了時刻`,scbd3558d2cfc7dc3:`全文`,sccad21b77f9a317c:j`最も高い種別: ${0}`,sccce3de7b4abfdfe:`モデルが応答を拒否`,scd945ec17b61f103:`エージェントの所要時間`,scdb3c8f0d50a81af:`Esc: 選択を解除`,scdece4ad70d57deb:`ループ`,sce26f796a9b94ef1:`各タスクが読み込むファイル（タスクの開始時に検証）`,scf1f6260b486064d:`一致する実行なし`,scf4185bf1a2d6adf:j`完了 ${0} 件`,scf70a5a7a06e1fa5:`レート制限`,sd1f67ae2a58049b0:`ファイルの検証に使うスキーマ`,sd3c028fcc08b18ab:`登録済みのタスクなし`,sd3ec6686aaaf1324:j`終了（未完了のタスク ${0} 件）`,sd47e3a005069edb9:`ローカルの認証情報（ambient）`,sd5a8fb496330927a:`ファイルに検証エラー`,sd5da7ee4a43a6b2d:j`トークン: 入力 ${0}、出力 ${1}、キャッシュ読み込み ${2}、キャッシュ書き込み ${3}`,sd68011705bf4b72f:`プロンプトは保存されていません（keep_transcripts = false）`,sd7338946b42394f4:`失敗`,sd7445330352af2c5:`検証対象のファイル`,sd747248fb64d7bb2:`なし（任意）`,sd757815e3da2dde5:`検証エラー`,sd7768c230e48ac70:j`全体の ${0}%`,sd77d82bf43357ecd:`実行中のエージェントのセッションの新しいイベント 1 件を表示`,sd794d5178cc31502:`出力が検証エラーになった後の、同じエージェントのセッションでの追加のラウンド（rounds）`,sd798aaccd0308806:`結果を受けて作成`,sd7d77bef673bd45f:j`入力 ${0}（${1} の出力）に検証エラー`,sd8284849892c5c5a:`タスクの開始前からあるファイルは無効`,sd93128c9fde34bb6:j`依存先タスク ${0} の出力待ち`,sda249baca3c52d27:j`セッション開始時の利用率: ${0}`,sda7d6c86fb627ba9:`失敗した回のあとにリトライしたタスク`,sda800fa8314eb82c:j`すべて表示（${0} 文字）`,sdb1595f5c742dfbb:`入力`,sdb80a6330c0fa072:`出力に検証エラー`,sdc40078597054827:j`実行グループ ${0}`,sdd0fb64c2928422f:`コーディングエージェントのイベント種別のうち、このバージョンの contraagent が対応していないもの`,sdd826d4b3e02f41b:`修正依頼なし`,sdf452c95fdeb4be0:`リトライなし`,sdf922ccc13491763:`リトライ後に完了`,se2788d18bd1f9873:`タスクを実行した CLI（claude、omp）`,se2bad0e4af9e9155:j`キー ${0} 個: ${1}`,se2cd8c3175e8f91f:j`期待する型: ${0}`,se3b4c857f91f80d7:`キーボードショートカット`,se5ad61b61dc5c4f6:`モデル切り替え`,se5d1247fe34fbb95:`monitor.Panel`,se60a4867465d5d31:`ハイコントラスト`,se61f0dc09b51fd35:`パイプラインのプロセス内の関数`,se66872955dc59191:`1 タスク`,se7102b7d5942a59c:j`${0} 回目`,se90f184c6aa3ffbb:`認証情報`,sea4f20ea1ece70a0:`定義`,sea67cb607ba79bea:`矢印キー: マーク`,sea748bf5cf6f28f3:j`${0} タスク`,sea7bdd2b70c8c2bb:`実行の一覧`,seac9afef1a00b5e8:`待機中`,sebada5168620c5fe:`既定`,sec2574ea71a53cc7:`すべての種別`,sec749d36a5ebf2a6:`コーディングエージェントが使ったエージェント定義（agents/&lt;role&gt;.md）`,secc170560fffe506:`上限に到達`,sed0a4ed4fcf1c063:`タスクごとに 1 つ（Backend.run）`,sed7bd1552ea928f8:`種別または関数`,sede9056322866918:`ステージなし`,seea0f53b4dbb2fb3:`結果`,seee13c69133b70b7:`スキップ`,sef0ce050d92c35e2:j`実行中 ${0} 件`,sefcf950b3cc4fc3b:`言語`,sf113fa256db9617b:`終了時刻`,sf14df172fd566bcc:`最初のエージェントのセッション`,sf2b0c091b94a0303:`トークンの報告なし`,sf2d62a5d815803af:j`関数 ${0}`,sf2e5c0d258c9b689:`定義`,sf39e43f2714690bc:`周回数`,sf3cb3cd43bbe95c2:`ほか 1 アカウント`,sf3e2e1c7b6313910:`カスタムビュー`,sf466a6f271f0b682:j`${0} 周目`,sf4897f85932ebf42:`終了後の利用率`,sf56cc81a8429fcb0:`試行の終了後に、同じアカウントで最初に報告された値`,sf5dbf772d898f6e7:`ユニットごとではなく、実行ごとに 1 回実行されるタスク`,sf6d770c86ee5a684:`フロー呼び出し`,sf6e66e6e9a5d83ff:`トランスクリプトは保存されていません（keep_transcripts = false）`,sf7b714930ed98b54:j`不明（${0}）`,sf93c7009f950942a:`合計`,sfa04f4ef1995407e:`テキスト`,sfa6a5b4597c720bc:`フィルターに一致するタスクなし`,sfadf0e9dfc4b3030:`修正依頼 1 回で完了`,sfb65f5d860c9a106:j`実行中のエージェントのセッション ${0} 件`,sfbb1f6b888aed522:`失敗した試行`,sfc7ed987d0fe9679:`再開カーソルなし`,sfd313341ca75a38d:j`リトライ後に完了 ${0} 件`,sfd5b8cae918b42cb:j`要素 ${0} 個: ${1}`,sfdd447bcde2c13ba:`プロセス`,sfddde3643e5505f4:`試行: 新しいエージェントのセッション`,sfde497acd6a6a561:`ファイルにない必須フィールド`,sfe771bfc3355dd51:j`${0}: 入力と出力`,sfe9c9abcded61e50:j`プロセス ${0}`,sff660af26c203189:`登録済みのタスクはまだありません`,sff6ef2732281bb26:`すべての試行が成功`,sff83af1548f682c0:j`${0} のタスク`,sffa12312d4ff4b9c:`定義なし`,sffb00562b267f0a5:`エージェントの起動に失敗`,sfff7f6b9ec291984:j`Python タスク ${0} 回`,"stage-done":`完了`,status:`状態`,"stop-completed":`完了`,"tab-tasks":`タスク`,tasks:`タスク`,"tokens-output":`出力`,"tool-done":`完了`,"view-graph":`グラフ`,"view-output":`出力`,"view-table":`表`},Qt={en:`English`,ja:`日本語`},$t=new Map([[`ja`,Xt]]),{getLocale:en,setLocale:tn}=Wt({sourceLocale:qt,targetLocales:Jt,loadLocale:e=>Promise.resolve($t.get(e))}),nn=`contraagent:locale`,rn=e=>Yt.includes(e);function an(){try{let e=globalThis.localStorage?.getItem(nn);if(rn(e))return e}catch{}for(let e of globalThis.navigator?.languages??[]){let t=e.toLowerCase().split(`-`)[0];if(rn(t))return t}return qt}async function on(e){try{globalThis.localStorage?.setItem(nn,e)}catch{}await tn(e)}var sn=e=>e&&e!==`neutral`?e:O;function cn(e,t,n){return e.dispatchEvent(new CustomEvent(t,{detail:n,bubbles:!0,composed:!0}))}function ln(e,t){let n={...e};if(t)for(let[e,r]of Object.entries(t))r!==void 0&&(n[e]=r);return n}function un(e,t){customElements.get(e)||customElements.define(e,t)}function P(e){if(e==null||Number.isNaN(e))return`—`;let t=Math.max(0,e);if(t<.05)return`<0.1s`;if(t<9.95)return`${t.toFixed(1)}s`;let n=Math.round(t);return n<60?`${n}s`:n<3600?`${Math.floor(n/60)}m ${String(n%60).padStart(2,`0`)}s`:`${Math.floor(n/3600)}h ${String(Math.floor(n%3600/60)).padStart(2,`0`)}m`}var F=e=>String(e??``).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`),dn=new Set,fn=null;function pn(){for(let e of dn)e.requestUpdate()}var mn=class{constructor(e){this.host=e,e.addController(this)}hostConnected(){dn.add(this.host),fn??=setInterval(pn,1e3)}hostDisconnected(){dn.delete(this.host),!dn.size&&fn&&(clearInterval(fn),fn=null)}},hn=new class{constructor(){this.seen=new Map}at(e,t,n=Date.now()){let r=Math.round(n-t*1e3),i=this.seen.get(e);return i!==void 0&&Math.abs(i-r)<5e3?i:(this.seen.set(e,r),r)}},gn=w`
  .tag { font-size: var(--font-size-xs); padding: 0 7px; border-radius: var(--radius-pill); border: 1px solid var(--line2); color: var(--text-muted); white-space: nowrap; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chip { font-size: var(--font-size-sm); padding: 1px 8px; border-radius: var(--radius-pill); border: 1px solid var(--line); color: var(--text-muted); white-space: nowrap; }
  .chip[data-tone='done'] { color: var(--text-2); }
  .chip[data-tone='done'] > [aria-hidden] { color: var(--tone); font-weight: 700; }
  .chip[data-tone='running'] { background: var(--tone); color: var(--bg); border-color: var(--tone); font-weight: 600; animation: ping 1.6s var(--ease) infinite; }
  .chip.todo { opacity: 0.65; }
  .taskchip { display: inline-block; font: inherit; font-family: var(--mono); font-size: var(--font-size-sm); line-height: 1.5; padding: 0 8px;
    border-radius: var(--radius-pill); border: 1px solid var(--line); background: var(--raise); color: var(--text-2); white-space: nowrap; }
  button.taskchip { cursor: pointer; }
  button.taskchip:hover { border-color: var(--accent); color: var(--text); }
  .kbd { font-family: var(--mono); font-size: var(--font-size-xs); border: 1px solid var(--line2); border-bottom-width: 2px;
    border-radius: var(--radius-sm); padding: 0 4px; color: var(--text-muted); }
`,_n=w`
  .g12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 14px; }
  .c12 { grid-column: span 12; }
  .c7 { grid-column: span 7; }
  .c5 { grid-column: span 5; }
  @media (max-width: 1150px) {
    .c7, .c5 { grid-column: span 12; }
  }
  .panel { background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
    border-radius: var(--radius-lg); padding: 14px 16px; min-width: 0; box-shadow: 0 10px 28px color-mix(in srgb, var(--shadow) 40%, transparent); }
  .panel > h3 { margin: 0 0 12px; display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 600; color: var(--text-2); }
  .panel > h3 .r { margin-left: auto; font-weight: 400; font-size: 11.5px; color: var(--text-muted); }
  .sect-h { margin: 14px 0 8px; font-size: var(--font-size-md); color: var(--text-2); font-weight: 600; }
  .sect-h .meta { margin-left: 8px; font-weight: 400; }

  .blank { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 60px 16px; color: var(--text-muted); text-align: center; }
  .blank .ic { font-size: 30px; opacity: 0.55; }
  .blank b { color: var(--text-2); font-weight: 600; }
  .blank a.lnk { text-decoration: underline; }
  .blank.small { padding: 24px; }

  /* a short clickable row (failures, launches) */
  .fl { padding: 7px 10px; border-radius: var(--radius-md); cursor: pointer; display: grid; grid-template-columns: auto 1fr auto; gap: 2px 10px; align-items: baseline; }
  .fl > .meta:last-child { grid-column: 1 / 4; overflow: hidden; text-overflow: ellipsis; }
  .fl:hover { background: var(--raise); }
`,vn=w`
  .enter { animation: enter 0.5s var(--ease) both; }

  @keyframes turn { to { transform: rotate(360deg); } }
  @keyframes breathe {
    0%, 100% { opacity: 0.45; box-shadow: 0 0 0 0 transparent; transform: scale(0.85); }
    50% { opacity: 1; box-shadow: 0 0 0 4px var(--status-running-bg); transform: scale(1); }
  }
  @keyframes ping { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--status-running) 55%, transparent); } 80%, 100% { box-shadow: 0 0 0 9px transparent; } }
  @keyframes enter { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  @keyframes bump { 0% { transform: scale(1); } 35% { transform: scale(1.04); box-shadow: 0 0 0 1px var(--line2); } 100% { transform: scale(1); } }
  @keyframes scan { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
  @keyframes growx { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  @keyframes stripes { to { background-position: 17px 0; } }
  @keyframes toast-in { from { opacity: 0; transform: translateY(12px) scale(0.97); } to { opacity: 1; transform: none; } }
  @keyframes toast-out { to { opacity: 0; transform: translateX(24px); } }
  @keyframes rowin { from { background: color-mix(in srgb, var(--text) 10%, transparent); } to { background: transparent; } }
  @keyframes bounce { 0%, 80%, 100% { transform: translateY(0); opacity: 0.45; } 40% { transform: translateY(-5px); opacity: 1; } }
  @keyframes core-beat { 0%, 100% { transform: scale(1); } 50% { transform: scale(0.72); } }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }
`,yn=w`
  *, *::before, *::after { box-sizing: border-box; }
  * { scrollbar-width: thin; scrollbar-color: var(--line2) transparent; }
  *:hover { scrollbar-color: var(--text-muted) transparent; }
  ::selection { background: var(--selection); }
  :focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; }
  button { font: inherit; color: inherit; }
  [hidden] { display: none !important; }
`,bn=w`
  /*
   * data-tone names its status colour, which each kind of status element below takes as
   * --tone (the colour) and --tone-bg (its tint). No data-tone: neutral.
   */
  [data-tone='failed'] { --tone: var(--status-failed); --tone-bg: var(--status-failed-bg); }
  [data-tone='attention'] { --tone: var(--status-attention); --tone-bg: var(--status-attention-bg); }
  [data-tone='done'] { --tone: var(--status-done); --tone-bg: var(--status-done-bg); }
  [data-tone='running'] { --tone: var(--status-running); --tone-bg: var(--status-running-bg); }
  [data-tone='muted'] { --tone: var(--status-muted); --tone-bg: var(--status-muted-bg); }

  /*
   * A status mark before a status word (data-mark): ✓ done, ✕ failed, ◌ not started or waiting.
   * The shape keeps the meaning without colour; screen readers read the word only.
   */
  [data-mark]::before { margin-right: 0.35em; font-weight: 700; }
  [data-mark='done']::before { content: '✓'; content: '✓' / ''; color: var(--status-done); }
  [data-mark='failed']::before { content: '✕'; content: '✕' / ''; }
  [data-mark='pending']::before { content: '◌'; content: '◌' / ''; }

  /* text in a status colour: only on a status that applies (a count above 0 of a problem, a status word) */
  .tone-text[data-tone] { color: var(--tone); }

  /*
   * A status as a pill, always with its word. A problem is tinted and marked (✕ failed, ◌ not started);
   * done is quiet (a ✓ and the word): it is the usual case, and the problems are what stand out.
   */
  .pill { border-radius: var(--radius-pill); padding: 1px 10px; font-size: var(--font-size-sm); font-weight: 500; background: var(--raise); color: var(--text-2); white-space: nowrap; }
  .pill[data-tone] { background: var(--tone-bg); color: var(--tone); }
  .pill[data-tone='done'] { background: none; padding-left: 2px; color: var(--text-2); }

  /* a status as a word in a row (History, Problems, Outputs): coloured for a problem, done quiet with its ✓ */
  .jstop { font-weight: 600; }
  .jstop[data-tone='failed'], .jstop[data-tone='attention'] { color: var(--tone); }
  .jstop[data-tone='done'] { color: var(--text-2); font-weight: 500; }

  /*
   * A status as a dot (a run in the header and the run list). The shape carries it too:
   * round done, square failed, diamond attention, a breathing ring running.
   */
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--line2); flex: none; display: inline-block; }
  .dot[data-tone] { background: var(--tone); }
  .dot[data-tone='running'] { animation: breathe 1.8s ease-in-out infinite; }
  .dot[data-tone='attention'] { border-radius: 1px; transform: rotate(45deg) scale(0.86); }
  .dot[data-tone='failed'] { border-radius: 1.5px; }
  .spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--status-running-bg);
    border-top-color: var(--status-running); animation: turn 0.9s linear infinite; flex: none; display: inline-block; }
`,xn=w`
  .jmono, code, .mono { font-family: var(--mono); }
  /* read by screen readers, not shown: the word beside a status mark or an icon */
  .sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .jmono { font-size: 11.5px; }
  .meta { color: var(--text-muted); font-size: var(--font-size-sm); }
  /* a label in a tight box: it wraps at spaces and between phrases, never inside a word (Japanese included) */
  .words { word-break: keep-all; overflow-wrap: break-word; line-break: strict; }
  /* one fact of a row in .words (factLine): the line breaks between facts first, inside one only when it is wider than the box */
  .words .f { display: inline-block; max-width: 100%; }
  @supports (word-break: auto-phrase) {
    .words:lang(ja) { word-break: auto-phrase; }
  }
  .mut, .jdim { color: var(--text-muted); }
  a.lnk { color: var(--accent); cursor: pointer; text-decoration: none; }
  a.lnk:hover { text-decoration: underline; }
`,Sn=s[a].tokens,Cn=w`
  :host {
    ${C(u.map(e=>e.derive?`--${e.name}: var(${e.prop}, ${e.derive});`:`--${e.name}: var(${e.prop}, var(${c(e.name)}, ${Sn[e.name]}));`).join(`
    `))}
    --sans: var(--ca-sans, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif);
    --mono: var(--ca-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace);
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    color-scheme: var(--ca-color-scheme, var(${C(c(`color-scheme`))}, ${C(s[a].scheme)}));
    color: var(--text);
  }
  :host([hidden]) {
    display: none !important;
  }
`,wn=w`
  .jtree { font-family: var(--mono); font-size: var(--font-size-md); overflow: auto; }
  .jt { margin-left: 16px; }
  details.jt > summary { cursor: pointer; list-style: revert; }
  .jk { color: var(--code-name); }
  .js { color: var(--code-string); }
  .jn { color: var(--code-number); }

  .md-p { margin: 0.15em 0; }
  .md-gap { height: 0.5em; }
  .md-h { font-weight: 600; margin: 0.7em 0 0.25em; }
  .md-h1 { font-size: 1.25em; }
  .md-h2 { font-size: 1.12em; }
  .md-h3 { font-size: 1.03em; color: var(--text-2); }
  .md-h4 { color: var(--text-2); }
  .md-li { padding-left: 16px; text-indent: -12px; margin: 0.1em 0; }
  .md-li::before { content: '• '; color: var(--text-muted); }
  .md-ol::before { content: ''; }
  .md-n { color: var(--text-muted); margin-right: 6px; }
  .md-q { border-left: 3px solid var(--line2); padding-left: 10px; color: var(--text-2); margin: 0.2em 0; }
  .md-hr { border: 0; border-top: 1px solid var(--line); margin: 0.7em 0; }
  .md-t { border-collapse: collapse; margin: 0.4em 0; }
  .md-t th, .md-t td { border: 1px solid var(--line); padding: 3px 9px; text-align: left; font-size: 12.5px; }
  .md-t th { background: var(--raise); }
  .md-doc { padding: 10px 14px; background: var(--well); border: 1px solid var(--line); border-radius: var(--radius-md); max-height: 460px; overflow: auto; line-height: 1.55; }
  .md-doc code, .tx code { background: var(--raise); border-radius: var(--radius-sm); padding: 0 4px; font-size: 0.92em; }
  .md-doc pre { background: var(--well); border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; white-space: pre-wrap; }
  .md-doc pre code, .tx pre code { background: none; padding: 0; border-radius: 0; font-size: inherit; }
  .md-front { margin-bottom: 10px; border-collapse: collapse; }
  .md-front td { padding: 2px 14px 2px 0; font-size: 12.5px; border: 0; vertical-align: top; }
  .md-front td:first-child { color: var(--text-muted); }
  .md-tele { color: var(--text-muted); font-size: 11.5px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .df-text { background: var(--well); border: 1px solid var(--line); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-md);
    white-space: pre-wrap; max-height: 420px; overflow: auto; margin: 0; }
  .df-tog { margin-left: auto; font-size: var(--font-size-sm); color: var(--accent); border: 1px solid var(--line2); border-radius: var(--radius-pill);
    padding: 0 9px; cursor: pointer; background: none; }
  .df-tog:hover { background: var(--accent-bg); }
  /* a template placeholder in a prompt */
  .pv { color: var(--code-constant); background: color-mix(in srgb, var(--code-constant) 12%, transparent); border-radius: var(--radius-sm); padding: 0 3px; }
  .pv.pc { color: var(--code-keyword); background: color-mix(in srgb, var(--code-keyword) 12%, transparent); }

  .hl { font-family: var(--mono); }
  .hl-k { color: var(--code-keyword); }
  .hl-const { color: var(--code-constant); font-style: italic; }
  .hl-s { color: var(--code-string); }
  .hl-doc { color: var(--code-string); font-style: italic; opacity: 0.85; }
  .hl-c { color: var(--code-comment); font-style: italic; }
  .hl-n { color: var(--code-number); }
  .hl-d { color: var(--code-function); }
  .hl-f { color: var(--code-function); font-weight: 600; }
  .hl-cls { color: var(--code-type); font-weight: 700; }
  .hl-t { color: var(--code-type); }
  .hl-b { color: var(--code-name); }
  .hl-key { color: var(--code-name); }
`,Tn=w`
  .jdur { position: relative; display: block; height: 6px; border-radius: 3px; background: var(--track); overflow: hidden; margin-top: 2px; }
  .jdur i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--meter); }
  .jdur i.bad { background: var(--status-failed); }
`,En=w`
  .drv-facts { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; font-size: var(--font-size-md); }
  .drv-facts i { font-style: normal; color: var(--text-muted); margin-right: 5px; font-size: var(--font-size-sm); }
`,I=[Cn,yn,xn,bn,gn,_n,vn];function Dn(e){switch(e){case`done`:return`done`;case`failed`:return`failed`;case`attention`:return`pending`;default:return null}}var On=e=>(e.mark===void 0||e.mark===!0?Dn(e.tone??`neutral`):e.mark||null)??O;function kn(e){let t=e.tone??`neutral`;return D`<span class="pill ${e.cls??``}" part="pill tone-${t}" data-tone=${sn(t)} data-mark=${On(e)} title=${e.title||O}>${e.text}</span>`}function An(e){let t=e.tone??`neutral`;return D`<span class="jstop ${e.cls??``}" part="status tone-${t}" data-tone=${sn(t)} data-mark=${On(e)} title=${e.title||O}>${e.text}</span>`}function jn(e,t){let n=t.tone??`neutral`;return D`<span class="${e} ${t.cls??``}" data-tone=${sn(n)} data-mark=${On(t)} title=${t.title||O}>${t.text}</span>`}var Mn={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Nn=e=>(...t)=>({_$litDirective$:e,values:t}),Pn=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}},Fn=`important`,In=` !`+Fn,Ln=Nn(class extends Pn{constructor(e){if(super(e),e.type!==Mn.ATTRIBUTE||e.name!==`style`||e.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(e){return Object.keys(e).reduce((t,n)=>{let r=e[n];return r==null?t:t+`${n=n.includes(`-`)?n:n.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,`-$&`).toLowerCase()}:${r};`},``)}update(e,[t]){let{style:n}=e.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let e of this.ft)t[e]??(this.ft.delete(e),e.includes(`-`)?n.removeProperty(e):n[e]=null);for(let e in t){let r=t[e];if(r!=null){this.ft.add(e);let t=typeof r==`string`&&r.endsWith(In);e.includes(`-`)||t?n.setProperty(e,t?r.slice(0,-11):r,t?Fn:``):n[e]=r}}return ze}}),Rn=e=>e.icon??(e.swatch||e.tone||e.shape||e.cls?D`<i class=${e.cls||O} data-tone=${sn(e.tone)} data-shape=${e.shape??O}
        style=${e.swatch?Ln({background:e.swatch}):O}></i>`:O);function zn(e,t={}){return D`<div class="legend ${t.cls??``}" part="legend" role="list" aria-label=${t.label||O}>
    ${e.map(e=>D`<span role="listitem" aria-hidden=${e.decorative?`true`:O}>${Rn(e)}${e.label}</span>`)}
  </div>`}var Bn=w`
  .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: var(--font-size-sm); color: var(--text-muted); }
  .legend > span { white-space: nowrap; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
  .legend i[data-tone] { background: var(--tone); }
  .legend i[data-shape='round'] { border-radius: 50%; }
  .legend i[data-shape='square'] { border-radius: 2px; }
  .legend i[data-shape='ring'] { background: none; border-radius: 50%; box-shadow: inset 0 0 0 1.5px var(--tone, var(--line2)); }
  .legend i[data-shape='hatched'] { border-radius: 2px; background: repeating-linear-gradient(135deg, transparent 0 2px, var(--tone, var(--line2)) 2px 3px); }
`;function Vn(e,t=` | `){let n=e.filter(e=>typeof e==`string`?e:e.text);return n.length?D`${n.map((e,n)=>typeof e==`string`?D`${n?t:``}<span class="f">${e}</span>`:D`${n?t:``}<span class="f tone-text" data-tone=${sn(e.tone)}>${e.text}</span>`)}`:O}var Hn=new Map;function Un(e,t,n={}){let r=Hn.get(e)??e;return t?D`<span class=${n.cls||O} part="icon" title=${t}><span aria-hidden="true">${r}</span><span class="sr">${t}</span></span>`:D`<span class=${n.cls||O} part="icon" aria-hidden="true">${r}</span>`}function Wn(e,t,n,r){if(e<=0)return null;let i=n=>n===t||n<0||n>=e?null:n;if(r.layout===`grid`){let a=Math.max(1,r.cols??1),o=Math.floor(t/a)*a;switch(n){case`ArrowRight`:return(t+1)%a&&t+1<e?i(t+1):null;case`ArrowLeft`:return t%a?i(t-1):null;case`ArrowDown`:return i(t+a);case`ArrowUp`:return i(t-a);case`Home`:return i(r.ctrl?0:o);case`End`:return i(r.ctrl?e-1:Math.min(o+a,e)-1);default:return null}}let[a,o]=r.layout===`horizontal`?[`ArrowLeft`,`ArrowRight`]:[`ArrowUp`,`ArrowDown`],s=n=>r.wrap?i((t+n+e)%e):i(t+n);switch(n){case o:return s(1);case a:return s(-1);case`Home`:return i(0);case`End`:return i(e-1);default:return null}}var Gn=class{constructor(e,t){this.host=e,this.o=t,this.current=0,this.onFocus=e=>{let t=this.indexOf(e);t>=0&&t!==this.current&&this.set(t)},this.onKey=e=>{let t=this.o.items(),n=this.indexOf(e);if(n<0)return;let r=Wn(t.length,n,e.key,{layout:this.o.layout,cols:this.o.columns?.(),wrap:this.o.wrap,ctrl:e.ctrlKey||e.metaKey}),i=r===null?void 0:t[r];r!==null&&i&&(e.preventDefault(),this.set(r),i.focus(),this.o.onMove?.(i,r))},e.addController(this)}hostConnected(){this.host.addEventListener(`keydown`,this.onKey),this.host.addEventListener(`focusin`,this.onFocus)}hostDisconnected(){this.host.removeEventListener(`keydown`,this.onKey),this.host.removeEventListener(`focusin`,this.onFocus)}hostUpdated(){this.sync()}set(e){this.current=e,this.sync()}sync(){let e=this.o.items();e.length&&(this.current=Math.min(Math.max(0,this.current),e.length-1),e.forEach((e,t)=>e.tabIndex=t===this.current?0:-1))}indexOf(e){return this.o.items().findIndex(t=>e.composedPath().includes(t))}},L=e=>(t,n)=>{n===void 0?customElements.define(e,t):n.addInitializer(()=>{customElements.define(e,t)})},Kn={attribute:!0,type:String,converter:fe,reflect:!1,hasChanged:pe},qn=(e=Kn,t,n)=>{let{kind:r,metadata:i}=n,a=globalThis.litPropertyMetadata.get(i);if(a===void 0&&globalThis.litPropertyMetadata.set(i,a=new Map),r===`setter`&&((e=Object.create(e)).wrapped=!0),a.set(n.name,e),r===`accessor`){let{name:r}=n;return{set(n){let i=t.get.call(this);t.set.call(this,n),this.requestUpdate(r,i,e,!0,n)},init(t){return t!==void 0&&this.C(r,void 0,e,t),t}}}if(r===`setter`){let{name:r}=n;return function(n){let i=this[r];t.call(this,n),this.requestUpdate(r,i,e,!0,n)}}throw Error(`Unsupported decorator location: `+r)};function R(e){return(t,n)=>typeof n==`object`?qn(e,t,n):((e,t,n)=>{let r=t.hasOwnProperty(n);return t.constructor.createProperty(n,e),r?Object.getOwnPropertyDescriptor(t,n):void 0})(e,t,n)}function z(e){return R({...e,state:!0,attribute:!1})}var Jn=(e,t,n)=>(n.configurable=!0,n.enumerable=!0,Reflect.decorate&&typeof t!=`object`&&Object.defineProperty(e,t,n),n);function Yn(e,t){return(n,r,i)=>{let a=t=>t.renderRoot?.querySelector(e)??null;if(t){let{get:e,set:t}=typeof r==`object`?n:i??(()=>{let e=Symbol();return{get(){return this[e]},set(t){this[e]=t}}})();return Jn(n,r,{get(){let n=e.call(this);return n===void 0&&(n=a(this),(n!==null||this.hasUpdated)&&t.call(this,n)),n}})}return Jn(n,r,{get(){return a(this)}})}}var{I:Xn}=$e,Zn=e=>e,Qn=()=>document.createComment(``),$n=(e,t,n)=>{let r=e._$AA.parentNode,i=t===void 0?e._$AB:t._$AA;if(n===void 0)n=new Xn(r.insertBefore(Qn(),i),r.insertBefore(Qn(),i),e,e.options);else{let t=n._$AB.nextSibling,a=n._$AM,o=a!==e;if(o){let t;n._$AQ?.(e),n._$AM=e,n._$AP!==void 0&&(t=e._$AU)!==a._$AU&&n._$AP(t)}if(t!==i||o){let e=n._$AA;for(;e!==t;){let t=Zn(e).nextSibling;Zn(r).insertBefore(e,i),e=t}}}return n},er=(e,t,n=e)=>(e._$AI(t,n),e),tr={},nr=(e,t=tr)=>e._$AH=t,rr=e=>e._$AH,ir=e=>{e._$AR(),e._$AA.remove()},ar=(e,t,n)=>{let r=new Map;for(let i=t;i<=n;i++)r.set(e[i],i);return r},B=Nn(class extends Pn{constructor(e){if(super(e),e.type!==Mn.CHILD)throw Error(`repeat() can only be used in text expressions`)}dt(e,t,n){let r;n===void 0?n=t:t!==void 0&&(r=t);let i=[],a=[],o=0;for(let t of e)i[o]=r?r(t,o):o,a[o]=n(t,o),o++;return{values:a,keys:i}}render(e,t,n){return this.dt(e,t,n).values}update(e,[t,n,r]){let i=rr(e),{values:a,keys:o}=this.dt(t,n,r);if(!Array.isArray(i))return this.ut=o,a;let s=this.ut??=[],c=[],l,u,d=0,f=i.length-1,p=0,m=a.length-1;for(;d<=f&&p<=m;)if(i[d]===null)d++;else if(i[f]===null)f--;else if(s[d]===o[p])c[p]=er(i[d],a[p]),d++,p++;else if(s[f]===o[m])c[m]=er(i[f],a[m]),f--,m--;else if(s[d]===o[m])c[m]=er(i[d],a[m]),$n(e,c[m+1],i[d]),d++,m--;else if(s[f]===o[p])c[p]=er(i[f],a[p]),$n(e,i[d],i[f]),f--,p++;else if(l===void 0&&(l=ar(o,p,m),u=ar(s,d,f)),l.has(s[d])){if(l.has(s[f])){let t=u.get(o[p]),n=t===void 0?null:i[t];if(n===null){let t=$n(e,i[d]);er(t,a[p]),c[p]=t}else c[p]=er(n,a[p]),$n(e,i[d],n),i[t]=null;p++}else ir(i[f]),f--}else ir(i[d]),d++;for(;p<=m;){let t=$n(e,c[m+1]);er(t,a[p]),c[p++]=t}for(;d<=f;){let e=i[d++];e!==null&&ir(e)}return this.ut=o,nr(e,c),ze}});function V(e,t,n,r){var i=arguments.length,a=i<3?t:r===null?r=Object.getOwnPropertyDescriptor(t,n):r,o;if(typeof Reflect==`object`&&typeof Reflect.decorate==`function`)a=Reflect.decorate(e,t,n,r);else for(var s=e.length-1;s>=0;s--)(o=e[s])&&(a=(i<3?o(a):i>3?o(t,n,a):o(t,n))||a);return i>3&&a&&Object.defineProperty(t,n,a),a}var or=class extends k{constructor(...e){super(...e),this.options=[],this.value=``,this.label=``,this.roving=new Gn(this,{items:()=>[...this.renderRoot.querySelectorAll(`button:not(:disabled)`)??[]],layout:`horizontal`,wrap:!0,onMove:e=>this.choose(e.dataset.value??``)})}static{this.styles=[I,w`
      :host { display: inline-flex; vertical-align: middle; }
      .group { display: inline-flex; border: 1px solid var(--line); border-radius: var(--cae-segmented-radius, 6px); overflow: hidden; }
      button { min-width: 22px; height: var(--cae-segmented-height, 20px); line-height: var(--cae-segmented-height, 20px); padding: var(--cae-segmented-padding, 0 10px);
        margin: 0; border: 0; border-radius: 0; background: none; font-size: var(--cae-segmented-font-size, 11.5px); text-align: center;
        color: var(--text-muted); cursor: pointer; }
      button + button { border-left: var(--cae-segmented-divider, 1px solid var(--line)); }
      button:hover { color: var(--cae-segmented-hover, var(--text)); }
      button[aria-checked='true'] { background: var(--raise); color: var(--text); cursor: default; }
      button:disabled { opacity: 0.5; cursor: default; }
      button:focus-visible { outline-offset: -2px; }
    `]}willUpdate(){let e=this.options.filter(e=>!e.disabled).findIndex(e=>e.value===this.value);e>=0&&(this.roving.current=e)}choose(e){e!==this.value&&(this.value=e,cn(this,`cae-change`,{value:e}))}render(){return D`<div class="group" part="group" role="radiogroup" aria-label=${this.label||O}>
      ${B(this.options,e=>e.value,e=>{let t=e.value===this.value;return D`<button type="button" role="radio" part=${t?`option option-selected`:`option`} aria-checked=${t?`true`:`false`}
            data-value=${e.value} lang=${e.lang||O} title=${e.title||O} ?disabled=${!!e.disabled}
            @click=${()=>this.choose(e.value)}>${e.label}</button>`})}
    </div>`}};V([R({attribute:!1})],or.prototype,`options`,void 0),V([R()],or.prototype,`value`,void 0),V([R()],or.prototype,`label`,void 0);var sr=e=>typeof e!=`object`||!e||(Array.isArray(e)?!e.length:!Object.keys(e).length),cr=class extends k{constructor(...e){super(...e),this.open=1}static{this.styles=[I,wn]}render(){return D`<div class="jtree" part="tree">${this.node(this.value,0)}</div>`}node(e,t){if(typeof e!=`object`||!e)return D`<span class=${typeof e==`string`?`js`:`jn`}>${JSON.stringify(e)??`undefined`}</span>`;let n=Array.isArray(e)?e.map((e,t)=>[t,e]):Object.entries(e);return n.length?D`${n.map(([e,n])=>sr(n)?D`<div class="jt"><span class="jk">${e}</span>: ${this.node(n,t+1)}</div>`:D`<details class="jt" ?open=${t<this.open}>
            <summary>
              <span class="jk">${e}</span>
              <span class="meta">${Array.isArray(n)?`[${n.length}]`:`{${Object.keys(n).length}}`}</span>
            </summary>
            ${this.node(n,t+1)}
          </details>`)}`:Array.isArray(e)?`[]`:`{}`}};V([R({attribute:!1})],cr.prototype,`value`,void 0),V([R({type:Number})],cr.prototype,`open`,void 0);var lr=new Set(`and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield`.split(` `)),ur=new Set([`None`,`True`,`False`,`self`,`cls`]),dr=new Set(`str int float bool list dict set tuple bytes object type len range print isinstance super Optional Literal Any Union Path`.split(` `)),fr=new RegExp([`(#[^\\n]*)`,`((?:[rRbBfFuU]{0,2})(?:"""[\\s\\S]*?"""|'''[\\s\\S]*?'''))`,`((?:[rRbBfFuU]{0,2})(?:"(?:[^"\\\\\\n]|\\\\.)*"|'(?:[^'\\\\\\n]|\\\\.)*'))`,`(@[A-Za-z_][\\w.]*)`,`(\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)`,`([A-Za-z_]\\w*)`].join(`|`),`g`);function pr(e){let t=``,n=0,r=``;fr.lastIndex=0;for(let i=fr.exec(e);i;i=fr.exec(e)){t+=F(e.slice(n,i.index)),n=fr.lastIndex;let[a,o,s,c,l,u,d]=i;if(o)t+=`<span class="hl-c">${F(a)}</span>`;else if(s)t+=`<span class="hl-s hl-doc">${F(a)}</span>`;else if(c)t+=`<span class="hl-s">${F(a)}</span>`;else if(l)t+=`<span class="hl-d">${F(a)}</span>`;else if(u)t+=`<span class="hl-n">${F(a)}</span>`;else if(d){let e=lr.has(d)?`hl-k`:ur.has(d)?`hl-k hl-const`:r===`class`?`hl-cls`:r===`def`?`hl-f`:dr.has(d)?`hl-b`:/^[A-Z]\w*$/.test(d)&&d.length>1&&/[a-z]/.test(d)?`hl-t`:``;t+=e?`<span class="${e}">${F(d)}</span>`:F(d),r=d;continue}/^\s*$/.test(a)||(r=``)}return t+F(e.slice(n))}function mr(e){let t=/("(?:[^"\\\n]|\\.)*")(\s*:)?|\b(true|false|null)\b|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)/g,n=``,r=0;for(let i=t.exec(e);i;i=t.exec(e)){n+=F(e.slice(r,i.index)),r=t.lastIndex;let[,a,o,s,c]=i;n+=a?o?`<span class="hl-key">${F(a)}</span>${F(o)}`:`<span class="hl-s">${F(a)}</span>`:s?`<span class="hl-k hl-const">${s}</span>`:`<span class="hl-n">${c??``}</span>`}return n+F(e.slice(r))}var hr={py:`python`,python:`python`,json:`json`,jsonc:`json`};function gr(e){let t=String(e||``).toLowerCase();return hr[t.replace(/^.*\./,``)]||hr[t]||``}function _r(e,t){let n=gr(t);return n===`python`?pr(e):n===`json`?mr(e):F(e)}function vr(e){return e.replace(/`([^`\n]+)`/g,`<code>$1</code>`).replace(/\*\*([^*\n]+)\*\*/g,`<b>$1</b>`).replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g,`$1<i>$2</i>`).replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g,`<a class="lnk" href="$2" target="_blank" rel="noopener">$1</a>`)}function yr(e){let t=[],n=0;for(;;){let r=e.indexOf("```",n);if(r<0)return t.push({t:`text`,s:e.slice(n)}),t;t.push({t:`text`,s:e.slice(n,r)});let i=e.indexOf(`
`,r+3),a=e.slice(r+3,i<0?e.length:i).trim(),o=i<0?e.length:i+1,s=e.indexOf("```",o);if(s<0)return t.push({t:`code`,s:e.slice(o),lang:a}),t;t.push({t:`code`,s:e.slice(o,s),lang:a}),n=s+3}}var br=/^\s*\|.*\|\s*$/;function xr(e){return yr(String(e||``)).map(e=>{if(e.t===`code`)return`<pre><code class="hl">${_r(e.s,e.lang)}</code></pre>`;let t=F(e.s).split(`
`),n=[];for(let e=0;e<t.length;e++){let r=t[e]??``,i;if(i=r.match(/^(#{1,6})\s+(.*)$/))n.push(`<div class="md-h md-h${Math.min(i[1].length,4)}">${vr(i[2])}</div>`);else if(/^\s*(-{3,}|\*{3,})\s*$/.test(r))n.push(`<hr class="md-hr">`);else if(i=r.match(/^\s*&gt;\s?(.*)$/))n.push(`<div class="md-q">${vr(i[1])}</div>`);else if(i=r.match(/^\s*[-*]\s+(.*)$/))n.push(`<div class="md-li">${vr(i[1])}</div>`);else if(i=r.match(/^\s*(\d+)[.)]\s+(.*)$/))n.push(`<div class="md-li md-ol"><span class="md-n">${i[1]}.</span>${vr(i[2])}</div>`);else if(br.test(r)&&/^\s*\|[\s:|-]+\|\s*$/.test(t[e+1]??``)){let i=e=>e.trim().replace(/^\||\|$/g,``).split(`|`).map(e=>vr(e.trim())),a=i(r);e+=2;let o=[];for(;e<t.length&&br.test(t[e]??``);)o.push(i(t[e++]??``));e--,n.push(`<table class="md-t"><tr>${a.map(e=>`<th>${e}</th>`).join(``)}</tr>`+o.map(e=>`<tr>${e.map(e=>`<td>${e}</td>`).join(``)}</tr>`).join(``)+`</table>`)}else n.push(r.trim()===``?`<div class="md-gap"></div>`:`<div class="md-p">${vr(r)}</div>`)}return n.join(``)}).join(``)}function Sr(e,t){let n=String(e||``),r=n.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/),i=``,a=n;if(r){a=r[2]??``;let e=(r[1]??``).split(`
`).map(e=>e.match(/^([\w-]+):\s*(.*)$/)).filter(e=>!!e).map(([,e,t])=>`<tr><td class="jmono">${F(e)}</td><td>${F(t)}</td></tr>`).join(``);i=e?`<table class="md-front">${e}</table>`:``}let o=xr(a);return`<div class="md-doc">${i}${t?t(o):o}</div>`}var Cr=class extends Pn{constructor(e){if(super(e),this.it=O,e.type!==Mn.CHILD)throw Error(this.constructor.directiveName+`() can only be used in child bindings`)}render(e){if(e===O||e==null)return this._t=void 0,this.it=e;if(e===ze)return e;if(typeof e!=`string`)throw Error(this.constructor.directiveName+`() called with a non-string value`);if(e===this.it)return this._t;this.it=e;let t=[e];return t.raw=t,this._t={_$litType$:this.constructor.resultType,strings:t,values:[]}}};Cr.directiveName=`unsafeHTML`,Cr.resultType=1;var wr=Nn(Cr),Tr={showRendered:`Show rendered`,showSource:`Show source`},Er=class extends k{constructor(...e){super(...e),this.text=``,this.strings={},this.source=!1}static{this.styles=[I,wn,w`
      :host { display: block; }
      .bar { display: flex; justify-content: flex-end; margin-bottom: 4px; }
    `]}render(){let e=ln(Tr,this.strings),{head:t,body:n}=this.split?.(this.text)??{head:``,body:this.text},r=Sr(n,this.transform);return D`<div class="bar">
        <button type="button" class="df-tog" part="toggle" @click=${()=>this.source=!this.source}>
          ${this.source?e.showRendered:e.showSource}</button>
      </div>
      ${this.source?D`<pre class="df-text">${this.text}</pre>`:D`${t?D`<div class="md-tele jmono">${t}</div>`:O}${wr(r)}`}`}};V([R()],Er.prototype,`text`,void 0),V([R({attribute:!1})],Er.prototype,`split`,void 0),V([R({attribute:!1})],Er.prototype,`transform`,void 0),V([R({attribute:!1})],Er.prototype,`strings`,void 0),V([z()],Er.prototype,`source`,void 0);var Dr=()=>globalThis.matchMedia?.(`(prefers-reduced-motion: reduce)`).matches??!1,Or=class extends k{constructor(...e){super(...e),this.value=0,this.shown=0,this.frame=0}createRenderRoot(){return this}willUpdate(e){if(!e.has(`value`))return;let t=this.shown,n=this.value;if(cancelAnimationFrame(this.frame),Dr()||t===n||!Number.isFinite(n)||!this.isConnected){this.shown=n;return}let r=performance.now(),i=e=>{let a=Math.min(1,(e-r)/700);this.shown=Math.round(t+(n-t)*(1-(1-a)**3)),a<1&&(this.frame=requestAnimationFrame(i))};this.frame=requestAnimationFrame(i)}disconnectedCallback(){super.disconnectedCallback(),cancelAnimationFrame(this.frame),this.shown=this.value}render(){return String(this.shown)}};V([R({type:Number})],Or.prototype,`value`,void 0),V([z()],Or.prototype,`shown`,void 0);var kr=class extends k{constructor(){super(),this.since=0,new mn(this)}createRenderRoot(){return this}render(){return this.since?P((Date.now()-this.since)/1e3):``}};V([R({type:Number})],kr.prototype,`since`,void 0);var Ar=new Map;function jr(e,t){let n=`${e}|${t}`,r=Ar.get(n);return r||(r=new Intl.DateTimeFormat(e,{...t?{month:`short`,day:`numeric`}:{},hour:`2-digit`,minute:`2-digit`,second:`2-digit`,hourCycle:`h23`}),Ar.set(n,r)),r}function Mr(e,t=!1,n=en()){if(!e)return``;let r=new Date(e);return Number.isNaN(r.getTime())?e:jr(n,t).format(r)}function Nr(e,t=Date.now()){let n=Date.parse(e||``);if(Number.isNaN(n))return``;let r=Math.max(0,(t-n)/1e3);return M(r<60?`just now`:r<3600?j`${Math.floor(r/60)}m ago`:r<86400?j`${Math.floor(r/3600)}h ago`:j`${Math.floor(r/86400)}d ago`)}var Pr=e=>e.charAt(0).toLocaleUpperCase(en())+e.slice(1),Fr=(...e)=>e.filter(e=>!!e),H=(...e)=>Fr(...e).join(` | `),Ir=new Map;function Lr(e,t=en()){let n=Ir.get(t);return n||(n=new Intl.ListFormat(t,{type:`conjunction`}),Ir.set(t,n)),n.format(e)}var U=(e,t=` · `)=>`${e.kind??``}${e.unit?t+e.unit:``}`;function Rr(e){let t=(e||``).trim();if(!t)return``;let n=(t.split(`
`)[0]||``).trim();return n.length>100?`${n.slice(0,100)}…`:n}function W(e){let t=e??0;return t<1e3?String(Math.round(t)):t<1e4?`${(t/1e3).toFixed(1).replace(/\.0$/,``)}k`:t<1e6?`${Math.round(t/1e3)}k`:`${(t/1e6).toFixed(1).replace(/\.0$/,``)}M`}function zr(e){return e==null?`—`:e===0?`$0`:e<.001?`<$0.001`:e<1?`$${e.toFixed(3)}`:`$${e.toFixed(2)}`}function Br(e){let t=new Map;for(let n of e)for(let[e,r]of Object.entries(n.unread_events??{}))t.set(e,(t.get(e)??0)+r);return[...t].map(([e,t])=>`${e} ×${t}`).join(`, `)}function Vr(e){return Hr(F(e))}var Hr=e=>e.replace(/\$\{?([A-Za-z_]\w*)\}?/g,`<span class="pv">$&</span>`).replace(/\{\{contract\}\}/g,`<span class="pv pc">{{contract}}</span>`);function Ur(e){let t=e.match(/^(TELEMETRY [^\n]*)\n+([\s\S]*)$/);return t?{head:t[1]??``,body:t[2]??``}:{head:``,body:e}}var Wr=`contraagent`,Gr=200,Kr=null,qr=``,Jr=null;function Yr(){let e=globalThis.history?.state;return e&&typeof e==`object`?e:{}}function Xr(){let e=Yr()[Wr];return e&&typeof e==`object`?e:{}}function Zr(){let e=Xr().entry;if(e)return e;let t=Math.random().toString(36).slice(2);return history.replaceState({...Yr(),[Wr]:{...Xr(),entry:t}},``),t}function Qr(){Jr&&clearTimeout(Jr),Jr=null;let e=Kr;Kr=null,e&&globalThis.history&&Xr().entry===qr&&history.replaceState({...Yr(),[Wr]:{...Xr(),...e}},``)}function $r(e){if(globalThis.history)return Kr&&qr===Xr().entry&&e in Kr?Kr[e]:Xr()[e]}function ei(e,t){if(!globalThis.history)return;let n=Zr();Kr&&qr!==n&&(Kr=null),qr=n,(Kr??={})[e]=t,Jr??=setTimeout(Qr,Gr)}function ti(){Qr()}globalThis.addEventListener?.(`pagehide`,ti);var ni=class{constructor(e){this.id=e,this.items=new Set($r(e)??[])}has(e){return this.items.has(e)}set(e,t){t!==this.items.has(e)&&(t?this.items.add(e):this.items.delete(e),ei(this.id,[...this.items]))}},ri=class{constructor(e){this.id=e;let t=null;try{t=JSON.parse(globalThis.sessionStorage?.getItem(`${Wr}:${e}`)??`null`)}catch{}this.items=new Set(Array.isArray(t)?t.filter(e=>typeof e==`string`):[])}has(e){return this.items.has(e)}set(e,t){if(t!==this.items.has(e)){t?this.items.add(e):this.items.delete(e);try{globalThis.sessionStorage?.setItem(`${Wr}:${this.id}`,JSON.stringify([...this.items]))}catch{}}}},ii=new Set([`launch`,`message_update`,`tool_execution_start`,`tool_execution_update`,`tool_execution_end`,`acall`,`aresult`,`message_start`,`message_end`,`turn_end`,`notice`,`auto_retry_start`]);function ai(e){return ii.has(e.type)?e:null}var oi=/\{[^{}]+\}/g,si=()=>typeof process==`object`&&Number.parseInt(process?.versions?.node?.substring(0,2))>=18&&process.versions.undici;function ci(){return Math.random().toString(36).slice(2,11)}function li(e){let{baseUrl:t=``,Request:n=globalThis.Request,fetch:r=globalThis.fetch,querySerializer:i,bodySerializer:a,pathSerializer:o,headers:s,requestInitExt:c=void 0,...l}={...e};c=si()?c:void 0,t=vi(t);let u=[];async function d(e,d){let{baseUrl:f,fetch:p=r,Request:m=n,headers:h,params:g={},parseAs:_=`json`,querySerializer:v,bodySerializer:y=a??hi,pathSerializer:b,body:x,middleware:ee=[],...S}=d||{},C=t;f&&(C=vi(f)??t);let w=typeof i==`function`?i:pi(i);v&&(w=typeof v==`function`?v:pi({...typeof i==`object`?i:{},...v}));let te=b||o||mi,ne=x===void 0?void 0:y(x,_i(s,h,g.header)),re=_i(ne===void 0||ne instanceof FormData?{}:{"Content-Type":`application/json`},s,h,g.header),ie=[...u,...ee],ae={redirect:`follow`,...l,...S,body:ne,headers:re},oe,se,T=new m(gi(e,{baseUrl:C,params:g,querySerializer:w,pathSerializer:te}),ae),E;for(let e in S)e in T||(T[e]=S[e]);if(ie.length){oe=ci(),se=Object.freeze({baseUrl:C,fetch:p,parseAs:_,querySerializer:w,bodySerializer:y,pathSerializer:te});for(let t of ie)if(t&&typeof t==`object`&&typeof t.onRequest==`function`){let n=await t.onRequest({request:T,schemaPath:e,params:g,options:se,id:oe});if(n){if(n instanceof m)T=n;else if(n instanceof Response){E=n;break}else throw Error(`onRequest: must return new Request() or Response() when modifying the request`)}}}if(!E){try{E=await p(T,c)}catch(t){let n=t;if(ie.length)for(let t=ie.length-1;t>=0;t--){let r=ie[t];if(r&&typeof r==`object`&&typeof r.onError==`function`){let t=await r.onError({request:T,error:n,schemaPath:e,params:g,options:se,id:oe});if(t){if(t instanceof Response){n=void 0,E=t;break}if(t instanceof Error){n=t;continue}throw Error(`onError: must return new Response() or instance of Error`)}}}if(n)throw n}if(ie.length)for(let t=ie.length-1;t>=0;t--){let n=ie[t];if(n&&typeof n==`object`&&typeof n.onResponse==`function`){let t=await n.onResponse({request:T,response:E,schemaPath:e,params:g,options:se,id:oe});if(t){if(!(t instanceof Response))throw Error(`onResponse: must return new Response() when modifying the response`);E=t}}}}let ce=E.headers.get(`Content-Length`);if(E.status===204||T.method===`HEAD`||ce===`0`&&!E.headers.get(`Transfer-Encoding`)?.includes(`chunked`))return E.ok?{data:void 0,response:E}:{error:void 0,response:E};if(E.ok)return{data:await(async()=>{if(_===`stream`)return E.body;if(_===`json`&&!ce){let e=await E.text();return e?JSON.parse(e):void 0}return await E[_]()})(),response:E};let le=await E.text();try{le=JSON.parse(le)}catch{}return{error:le,response:E}}return{request(e,t,n){return d(t,{...n,method:e.toUpperCase()})},GET(e,t){return d(e,{...t,method:`GET`})},PUT(e,t){return d(e,{...t,method:`PUT`})},POST(e,t){return d(e,{...t,method:`POST`})},DELETE(e,t){return d(e,{...t,method:`DELETE`})},OPTIONS(e,t){return d(e,{...t,method:`OPTIONS`})},HEAD(e,t){return d(e,{...t,method:`HEAD`})},PATCH(e,t){return d(e,{...t,method:`PATCH`})},TRACE(e,t){return d(e,{...t,method:`TRACE`})},use(...e){for(let t of e)if(t){if(typeof t!=`object`||!(`onRequest`in t||`onResponse`in t||`onError`in t))throw Error("Middleware must be an object with one of `onRequest()`, `onResponse() or `onError()`");u.push(t)}},eject(...e){for(let t of e){let e=u.indexOf(t);e!==-1&&u.splice(e,1)}}}}function ui(e,t,n){if(t==null)return``;if(typeof t==`object`)throw Error("Deeply-nested arrays/objects aren’t supported. Provide your own `querySerializer()` to handle these.");return`${e}=${n?.allowReserved===!0?t:encodeURIComponent(t)}`}function di(e,t,n){if(!t||typeof t!=`object`)return``;let r=[],i={simple:`,`,label:`.`,matrix:`;`}[n.style]||`&`;if(n.style!==`deepObject`&&n.explode===!1){for(let e in t)r.push(e,n.allowReserved===!0?t[e]:encodeURIComponent(t[e]));let i=r.join(`,`);switch(n.style){case`form`:return`${e}=${i}`;case`label`:return`.${i}`;case`matrix`:return`;${e}=${i}`;default:return i}}for(let i in t){let a=n.style===`deepObject`?`${e}[${i}]`:i;r.push(ui(a,t[i],n))}let a=r.join(i);return n.style===`label`||n.style===`matrix`?`${i}${a}`:a}function fi(e,t,n){if(!Array.isArray(t))return``;if(n.explode===!1){let r={form:`,`,spaceDelimited:`%20`,pipeDelimited:`|`}[n.style]||`,`,i=(n.allowReserved===!0?t:t.map(e=>encodeURIComponent(e))).join(r);switch(n.style){case`simple`:return i;case`label`:return`.${i}`;case`matrix`:return`;${e}=${i}`;default:return`${e}=${i}`}}let r={simple:`,`,label:`.`,matrix:`;`}[n.style]||`&`,i=[];for(let r of t)n.style===`simple`||n.style===`label`?i.push(n.allowReserved===!0?r:encodeURIComponent(r)):i.push(ui(e,r,n));return n.style===`label`||n.style===`matrix`?`${r}${i.join(r)}`:i.join(r)}function pi(e){return function(t){let n=[];if(t&&typeof t==`object`)for(let r in t){let i=t[r];if(i!=null){if(Array.isArray(i)){if(i.length===0)continue;n.push(fi(r,i,{style:`form`,explode:!0,...e?.array,allowReserved:e?.allowReserved||!1}));continue}if(typeof i==`object`){n.push(di(r,i,{style:`deepObject`,explode:!0,...e?.object,allowReserved:e?.allowReserved||!1}));continue}n.push(ui(r,i,e))}}return n.join(`&`)}}function mi(e,t){let n=e;for(let r of e.match(oi)??[]){let e=r.substring(1,r.length-1),i=!1,a=`simple`;if(e.endsWith(`*`)&&(i=!0,e=e.substring(0,e.length-1)),e.startsWith(`.`)?(a=`label`,e=e.substring(1)):e.startsWith(`;`)&&(a=`matrix`,e=e.substring(1)),!t||t[e]===void 0||t[e]===null)continue;let o=t[e];if(Array.isArray(o)){n=n.replace(r,fi(e,o,{style:a,explode:i}));continue}if(typeof o==`object`){n=n.replace(r,di(e,o,{style:a,explode:i}));continue}if(a===`matrix`){n=n.replace(r,`;${ui(e,o)}`);continue}n=n.replace(r,a===`label`?`.${encodeURIComponent(o)}`:encodeURIComponent(o))}return n}function hi(e,t){return e instanceof FormData?e:t&&(t.get instanceof Function?t.get(`Content-Type`)??t.get(`content-type`):t[`Content-Type`]??t[`content-type`])===`application/x-www-form-urlencoded`?new URLSearchParams(e).toString():JSON.stringify(e)}function gi(e,t){let n=`${t.baseUrl}${e}`;t.params?.path&&(n=t.pathSerializer(n,t.params.path));let r=t.querySerializer(t.params.query??{});return r.startsWith(`?`)&&(r=r.substring(1)),r&&(n+=`?${r}`),n}function _i(...e){let t=new Headers;for(let n of e){if(!n||typeof n!=`object`)continue;let e=n instanceof Headers?n.entries():Object.entries(n);for(let[n,r]of e)if(r===null)t.delete(n);else if(Array.isArray(r))for(let e of r)t.append(n,e);else r!==void 0&&t.set(n,r)}return t}function vi(e){return e.endsWith(`/`)?e.substring(0,e.length-1):e}var yi=class extends Error{constructor(e,t){super(`${e} ${t}`),this.status=e,this.path=t,this.name=`ApiError`}};async function bi(e){let{data:t,response:n}=await e;if(!n.ok||t===void 0)throw new yi(n.status,new URL(n.url,`http://x`).pathname);return t}function xi(e={}){let t=(e.baseUrl??``).replace(/\/$/,``),n=li({baseUrl:t||globalThis.location?.origin||``,...e.fetch?{fetch:e.fetch}:{}});return{baseUrl:t,info:()=>bi(n.GET(`/api/info`)),runs:()=>bi(n.GET(`/api/runs`)),journal:(e,t=0)=>bi(n.GET(`/api/runs/{run}/journal`,{params:{path:{run:e},query:{since:t}}})),definitions:e=>bi(n.GET(`/api/runs/{run}/definitions`,{params:{path:{run:e}}})),task:(e,t)=>bi(n.GET(`/api/runs/{run}/task/{key}`,{params:{path:{run:e,key:t}}})),stream:(e,t,r=0)=>bi(n.GET(`/api/runs/{run}/stream/{key}`,{params:{path:{run:e,key:t},query:{since:r}}})),panel:(e,t)=>bi(n.GET(`/api/runs/{run}/panels/{name}`,{params:{path:{run:e,name:t}}}))}}var Si=[`journal`,`procs`,`plan`,`outputs`,`cursor`,`ready`];function Ci(e,t,n,r){let i=new(r.EventSource??globalThis.EventSource)(e);i.onopen=()=>n.open?.(),i.onerror=()=>n.error?.();for(let e of t)i.addEventListener(e,t=>{n.message({event:e,data:JSON.parse(t.data)})});return()=>i.close()}var wi=encodeURIComponent;function Ti(e,t,n,r={}){let i=[...Si,...t.map(e=>`panel:${e}`)];return Ci(`${r.baseUrl??``}/events?run=${wi(e)}`,i,n,r)}function Ei(e,t,n,r={}){return Ci(`${r.baseUrl??``}/events/stream?run=${wi(e)}&key=${wi(t)}`,[`stream`],{...n,message:e=>n.message(e.data)},r)}var Di=4e3;function Oi(){return{journal:[],procs:null,plan:{nodes:[],groups:[],flow_calls:[]},outputs:{contracts:[],tally:{valid:0,invalid:0,refused:0,pending:0,failed:0,running:0}},cursor:null,panels:{},ready:!1}}function ki(e,t){let n=e,r=null,i=()=>{if(!r)return;let e=n.journal.concat(r);n={...n,journal:e.length>4e3?e.slice(e.length-Di):e},r=null};for(let e of t){if(e.event===`journal`){(r??=[]).push(e.data);continue}switch(i(),e.event){case`connected`:n={...n,journal:[],ready:!1};break;case`ready`:n={...n,ready:!0};break;case`procs`:n={...n,procs:e.data};break;case`plan`:n={...n,plan:e.data};break;case`outputs`:n={...n,outputs:e.data};break;case`cursor`:n={...n,cursor:e.data};break;default:n={...n,panels:{...n.panels,[e.event.slice(6)]:e.data}}}}return i(),n}var Ai=e=>!!e.stop&&e.stop!==`completed`&&e.stop!==`skipped`,G=e=>e.executor===`python`;function ji(e){let t=0;return e.map((n,r)=>{let i=e[r-1];return i&&(n.attempt??0)<=(i.attempt??0)&&t++,t})}var Mi=e=>`${e.ts}|${e.key}`,Ni=(e,t)=>e.find(e=>e.run===t),Pi=(e,t)=>!!e.procs?.alive||!!t?.running;function Fi(e){return e?[...e.launches.map(e=>({cls:`llm`,id:`c:${e.key}`,kind:e.kind||`task`,unit:e.unit||``,detail:[e.unit,e.model||e.role].filter(Boolean).join(` | `),ageS:e.age_s,key:e.key})),...e.python_tasks.map(e=>({cls:`py`,id:`p:${e.key}`,kind:e.kind||`task`,unit:e.unit||``,detail:e.unit||`Python`,ageS:e.age_s,key:``}))]:[]}var Ii={title:`contraagent`,panels:[],api_version:``},Li=class{constructor(e={}){this.snap={info:Ii,runs:[],run:``,state:Oi(),connected:!1,fresh:new Set},this.listeners=new Set,this.rowListeners=new Set,this.closeFeed=null,this.queue=[],this.flushTimer=null,this.pollTimer=null,this.opts={runsEveryMs:5e3,batchMs:50,freshMs:4e3,...e},this.client=e.client??xi(e.baseUrl===void 0?{}:{baseUrl:e.baseUrl})}get snapshot(){return this.snap}subscribe(e){return this.listeners.add(e),()=>this.listeners.delete(e)}onNewRow(e){return this.rowListeners.add(e),()=>this.rowListeners.delete(e)}async start(){try{let e=this.panelNames();this.set({info:await this.client.info()}),this.snap.run&&this.panelNames()!==e&&this.reopen()}catch{}await this.refreshRuns(),this.pollTimer??=setInterval(()=>void this.refreshRuns(),this.opts.runsEveryMs)}async refreshRuns(){try{this.set({runs:await this.client.runs()})}catch{}}panelNames(){return this.snap.info.panels.map(e=>e.name).join(`
`)}reopen(){let e=this.snap.run;this.closeFeed?.(),this.closeFeed=null,this.selectRun(e)}selectRun(e){(e!==this.snap.run||!this.closeFeed&&e)&&(this.closeFeed?.(),this.closeFeed=null,this.queue=[],this.set({run:e,state:Oi(),connected:!1,fresh:new Set}),e&&(this.closeFeed=Ti(e,this.snap.info.panels.map(e=>e.name),{open:()=>{this.push({event:`connected`}),this.set({connected:!0})},error:()=>this.set({connected:!1}),message:e=>this.push(e)},{...this.opts.baseUrl===void 0?{}:{baseUrl:this.opts.baseUrl},...this.opts.feed})))}stop(){this.closeFeed?.(),this.closeFeed=null,this.pollTimer&&clearInterval(this.pollTimer),this.pollTimer=null,this.flushTimer&&clearTimeout(this.flushTimer),this.flushTimer=null}push(e){this.queue.push(e),this.flushTimer??=setTimeout(()=>this.flush(),this.opts.batchMs)}flush(){this.flushTimer=null;let e=this.queue;this.queue=[];let t=this.snap.state.ready,n=[];for(let r of e)r.event===`connected`?t=!1:r.event===`ready`?t=!0:r.event===`journal`&&t&&n.push(r.data);let r=ki(this.snap.state,e);if(!n.length){this.set({state:r});return}let i=new Set(this.snap.fresh);for(let e of n)i.add(Mi(e));this.set({state:r,fresh:i});for(let e of n)for(let t of this.rowListeners)t(e);setTimeout(()=>{let e=new Set(this.snap.fresh);for(let t of n)e.delete(Mi(t));this.set({fresh:e})},this.opts.freshMs)}set(e){this.snap={...this.snap,...e};for(let e of this.listeners)e(this.snap)}},Ri=e=>e.ok,K=e=>e.stop!==`invalid_input`&&e.stop!==`skipped`;function zi(e,t){if(e?.state===`running`)return`running`;let n=t[t.length-1];return n?n.stop===`skipped`?`skipped`:n.stop===`invalid_input`?`not_started`:Ri(n)?t.some(e=>K(e)&&!Ri(e))?`recovered`:`done`:`failed`:e?.state===`blocked`?`not_started`:`waiting`}function Bi(e){let t=new Set,n=[];for(let r of e)K(r)&&(t.has(r.key)&&n.push(r),Ri(r)||t.add(r.key));return n}function Vi(e){switch(e){case`blocked`:return`not_started`;case`pending`:return`waiting`;default:return e}}var Hi=e=>e===`done`||e===`recovered`||e===`skipped`;function Ui(e,t){let n=new Map;for(let t of e){let e=n.get(t.key);e||n.set(t.key,e=[]),e.push(t)}let r=new Map(t.nodes.map(e=>[e.key,e])),i=[...new Set([...t.nodes.map(e=>e.key),...n.keys()])],a=new Map;for(let e of i){let t=r.get(e),i=n.get(e)??[],o=i[0];a.set(e,{key:e,kind:t?.kind??o?.kind??``,unit:t?.unit??o?.unit??``,executor:t?.executor??o?.executor??`agent`,outcome:zi(t,i),attempts:i,tries:i.filter(K),cause:null})}let o=(e,t)=>{for(let n of r.get(e)?.after??[]){if(t.has(n))continue;t.add(n);let e=a.get(n);if(e?.outcome===`failed`)return n;if(e?.outcome===`not_started`){let e=o(n,t);if(e)return e}}return null};for(let e of a.values())e.outcome===`not_started`&&(e.cause=o(e.key,new Set));return a}function Wi(e){let t=new Map;for(let n of e.values())n.outcome===`failed`&&t.set(n.key,{task:n,stopped:[]});let n=[];for(let r of e.values()){if(r.outcome!==`not_started`)continue;let e=r.cause?t.get(r.cause):void 0;e?e.stopped.push(r):n.push(r)}let r=e=>e.attempts[e.attempts.length-1]?.ts??``;return{failed:[...t.values()].sort((e,t)=>r(t.task).localeCompare(r(e.task))),notStarted:n,recovered:[...e.values()].filter(e=>e.outcome===`recovered`)}}function Gi(e){let t={done:0,recovered:0,failed:0,not_started:0,running:0,waiting:0,skipped:0,total:0};for(let n of e.values())t[n.outcome]++,t.total++;return t}function Ki(e){let t=Array.isArray(e?.flow)?e.flow:[];for(let e=t.length-1;e>=0;e--){let n=t[e]?.loops??[],r=n[n.length-1];if(r)return typeof r.pass==`number`&&r.pass>=1?r.pass:1}return null}function qi(e,t){let n=new Map(t.nodes.map(e=>[e.key,e]));return[...e.values()].map(t=>{let r=t.attempts[t.attempts.length-1],i=n.get(t.key);return{...t,pass:Ki(i),wall_s:t.tries.reduce((e,t)=>e+(t.wall_s||0),0),last_ts:r?.ts??``,last_stop:r?.stop??``,waits_for:t.outcome===`waiting`?(i?.after??[]).filter(t=>!Hi(e.get(t)?.outcome??`waiting`)):[]}})}function Ji(e){let t=e.filter(e=>e.executor!==`python`),n=t.find(e=>e.outcome===`running`);if(n)return n.key;let r=e=>e.tries[e.tries.length-1]?.ts??``;return t.filter(r).sort((e,t)=>r(t).localeCompare(r(e)))[0]?.key??null}var Yi={nodes:[],groups:[]},Xi=new WeakMap;function Zi(e,t=Yi){let n=t??Yi,r=Xi.get(e);r||Xi.set(e,r=new WeakMap);let i=r.get(n);return i||r.set(n,i=Qi(e,n)),i}function Qi(e,t){let n=Ui(e,t),r=Gi(n);return{outcomes:n,rows:qi(n,t),counts:{...r,doneTotal:r.done+r.recovered,finished:r.done+r.recovered+r.skipped},problems:Wi(n),kinds:[...new Set([...n.values()].map(e=>e.kind))].sort(),tries:$i(e)}}function $i(e){let t=e.filter(K).length;return{tries:t,notStarted:e.length-t}}function ea(e){let t=e.groups.reduce((e,t)=>e+t.total,0),n=e.groups.reduce((e,t)=>e+t.done,0),r=e.groups.reduce((e,t)=>e+t.skipped,0);return{total:t,done:n,skipped:r,pct:Math.round(100*(n+r)/Math.max(1,t))}}function ta(e){let t=(...t)=>e.nodes.filter(e=>t.includes(e.state)).length;return{done:t(`done`),skipped:t(`skipped`),failed:t(`failed`),notStarted:t(`blocked`),left:t(`pending`,`running`)}}function na(e){let t=Date.parse(e?.started_at??``),n=Date.parse(e?.last_ts??``);return Number.isNaN(t)||Number.isNaN(n)?null:Math.max(0,(n-t)/1e3)}var ra=()=>({input:0,output:0,cache_read:0,cache_creation:0,calls:0,cost:null,reported:0}),ia=e=>e.input+e.output+e.cache_read+e.cache_creation;function aa(e,t){let n=t.usage;return!n&&(t.cost_usd===null||t.cost_usd===void 0)?e:(n&&(e.input+=n.input??0,e.output+=n.output??0,e.cache_read+=n.cache_read??0,e.cache_creation+=n.cache_creation??0,e.calls+=n.calls??0),t.cost_usd!==null&&t.cost_usd!==void 0&&(e.cost=(e.cost??0)+t.cost_usd),e.reported++,e)}function oa(e){let t=ra();for(let n of e)aa(t,n);return t.reported?t:null}function sa(e,t){let n=new Map,r=ra();for(let i of e){aa(r,i);let e=t(i),a=n.get(e);a||n.set(e,a={id:e,kind:i.kind,unit:i.unit??``,spend:ra(),share:null}),aa(a.spend,i)}let i=[...n.values()].filter(e=>e.spend.reported);for(let e of i)e.share=r.cost?(e.spend.cost??0)/r.cost:null;return i.sort((e,t)=>(t.spend.cost??0)-(e.spend.cost??0)||ia(t.spend)-ia(e.spend))}var ca=e=>sa(e,e=>e.key),la=e=>sa(e,e=>e.kind).map(e=>({...e,unit:``})),ua=e=>Date.parse(e.observed_at??``),da=e=>!Number.isNaN(ua(e))&&(e.five_hour_pct!=null||e.seven_day_pct!=null);function fa(e){let t=[];for(let n of e)for(let e of n.quota??[])da(e)&&t.push({reading:e,key:n.key,attempt:n.attempt??0});return t.sort((e,t)=>ua(e.reading)-ua(t.reading))}function pa(e){let t=new Map;for(let{reading:n}of fa(e)){let e=n.credential??``,r=t.get(e);r||t.set(e,r=[]),r.push(n)}let n=[];for(let[e,r]of t){let t=r[0],i=r[r.length-1];t&&i&&n.push({credential:e,first:t,last:i})}return n.sort((e,t)=>(t.last.seven_day_pct??0)-(e.last.seven_day_pct??0))}function ma(e,t){let n=(e.quota??[]).filter(da).sort((e,t)=>ua(e)-ua(t)),r=Date.parse(e.ts),i=n[0]??null,a=i?.credential??``;return{start:i,next:(i===null||Number.isNaN(r)?void 0:t.find(e=>ua(e.reading)>r&&(e.reading.credential??``)===a))?.reading??null}}function ha(e){let t=/^invalid input:\s*(.*)$/s.exec(e||``);if(!t)return[];let n=[];for(let e of(t[1]??``).split(`; `)){let t=/^input from (\S+) is missing: (\S+)/.exec(e);if(t){n.push({path:t[2]??``,producer:t[1]??``,problem:`missing`});continue}if(t=/^(\S+?): required input is missing/.exec(e),t){n.push({path:t[1]??``,producer:``,problem:`missing`});continue}t=/^(\S+?): /.exec(e),t&&!n.some(e=>e.path===t?.[1])&&n.push({path:t[1]??``,producer:``,problem:`checks`})}return n}function q(e,t){if(!e||!t)return e??``;let n=t.replace(/[.*+?^${}()|[\]\\]/g,`\\$&`);return e.replace(RegExp(`(?:/[^\\s:'"]*)?/${n}/`,`g`),``)}function ga(e){let t=e[0];return t?e.length===1?M(j`waits for output of ${U(t)}`):M(j`waits for output of ${e.length} earlier tasks`):``}function _a(e,t,n){return t===`checks`?M(n?j`input ${e} from ${n.name} failed checks`:j`input ${e} failed checks`):n?n.outcome===`failed`?M(j`input ${e} is missing because ${n.name} failed`):n.outcome===`not_started`?M(j`input ${e} is missing because ${n.name} did not start`):n.outcome&&Hi(n.outcome)?M(j`input ${e} from ${n.name} is missing`):M(j`input ${e} is missing because ${n.name} did not finish`):M(j`input ${e} is missing`)}function va(e,t,n,r){let i=e.attempts[e.attempts.length-1];if(i?.stop===`invalid_input`){let e=ha(i.reason)[0];if(!e)return q(i.reason,n);let a=e.producer||r?.(e.path)||``,o=a?t.get(a):void 0;return _a(q(e.path,n),e.problem,o?{name:U(o),outcome:o.outcome}:void 0)}let a=e.cause?t.get(e.cause):void 0;return a?M(j`earlier task ${U(a)} failed`):``}function ya(e){switch(e){case`valid`:return M(`passed`);case`invalid`:return M(`failed checks`);case`refused`:return M(`not written (task not started)`);case`failed`:return M(`not written (task failed)`);case`running`:return M(`not written yet (task running)`);case`pending`:return M(`not written yet (task waiting)`)}}function ba(e){switch(e){case`refused`:return M(`The task did not start because an input was missing or failed checks`);case`valid`:return M(`The file passed its checks`);case`invalid`:return M(`The file failed its checks`);case`failed`:return M(`The task failed before it wrote a file that passes its checks`);case`running`:return M(`The task is running`);case`pending`:return M(`The task is waiting`)}}var xa=()=>M(`Correction: another round in the same agent session after the output failed checks`);function Sa(e,t){let n=(e??1)-1;return n<1?``:M(t?n===1?`after 1 correction`:j`after ${n} corrections`:n===1?`1 correction`:j`${n} corrections`)}function Ca(e,t,n){let r=e.errors??[],i=ha(`invalid input: ${r.map(e=>e.replace(/^invalid input:\s*/,``)).join(`; `)}`)[0];if(!i)return r[0]?Pr(q(r[0],t)):M(`An input was missing or failed checks`);let a=n?.(i.path);return Pr(_a(q(i.path,t),i.problem,a))}function wa(e,t){return e>0?t:`neutral`}function Ta(e,t){return e?`running`:t?.total?t.failed?`failed`:t.not_started?`attention`:`done`:`neutral`}var Ea={completed:`done`,invalid_input:`attention`,skipped:`muted`,timeout:`failed`,max_turns:`failed`,budget:`failed`,context_budget:`failed`,stalled:`failed`,auth_failed:`failed`,api_error:`failed`,rate_limited:`failed`,refused:`failed`,aborted:`failed`,denied:`failed`,error:`failed`,no_output:`failed`,launch_failed:`failed`,invalid_output:`failed`,credential_mismatch:`failed`};Object.keys(Ea);var Da=e=>e!=null&&Object.hasOwn(Ea,e);function Oa(e){return Da(e)?Ea[e]:`failed`}function ka(e){switch(e){case`done`:case`recovered`:return`done`;case`failed`:return`failed`;case`not_started`:return`attention`;case`running`:return`running`;case`waiting`:case`skipped`:return`muted`}}function Aa(e){switch(e){case`valid`:return`done`;case`invalid`:case`failed`:return`failed`;case`refused`:return`attention`;case`running`:return`running`;case`pending`:return`muted`;case null:case void 0:return`neutral`}}var ja=e=>e===`waiting`?`pending`:Dn(ka(e));un(`cae-json-tree`,cr);var Ma=(e,t,n=``)=>D`<span class="fk ${e?`ok`:`bad`}" title=${n||O}><span aria-hidden="true">${e?`✓`:`✕`}</span> ${t}</span>`;function Na(e){let t=!!e.file.exists;return jn(`ct-chip`,{text:t?M(`found`):e.required?M(`missing (required)`):M(`missing (optional)`),tone:t?`done`:e.required?`failed`:`muted`})}function Pa(e,t){return e?jn(`ct-chip`,{text:t===void 0?ya(e):D`${ya(e)} <b>${t}</b>`,tone:Aa(e),title:ba(e)}):jn(`ct-chip`,{text:`—`})}function Fa(e,t){return e.startsWith(`list[`)||e===`array`?Array.isArray(t):e===`string`?typeof t==`string`:e===`integer`?Number.isInteger(t):e===`number`?typeof t==`number`:e===`boolean`?typeof t==`boolean`:e!==`object`||typeof t==`object`&&!!t&&!Array.isArray(t)}var Ia=(e,t)=>e.length>t?`${e.slice(0,t)}…`:e;function La(e){if(e===void 0)return D`<span class="jdim">—</span>`;if(typeof e==`string`)return D`<span class="js" title=${e}>"${Ia(e,90)}"</span>`;if(Array.isArray(e)){let t=e.slice(0,3).map(e=>typeof e==`string`?`"${Ia(e,28)}"`:JSON.stringify(e)).join(`, `);return D`<span class="jn">${e.length===1?M(`1 item`):M(j`${e.length} items`)}</span>
      <span class="jdim">${t}${e.length>3?`, …`:``}</span>`}return typeof e==`object`&&e?D`<span class="jn">${M(`object`)}</span> <span class="jdim">${Object.keys(e).slice(0,4).join(`, `)}</span>`:D`<span class="jn">${JSON.stringify(e)}</span>`}function Ra(e){let t=e.content;return typeof t==`object`&&t?D`<cae-json-tree .value=${t}></cae-json-tree>`:D`<pre class="jtree">${typeof t==`string`?t:M(`Not JSON`)}</pre>`}var za=e=>/^RootModel\[(.+)\]$/.exec(e)?.[1]??null;function Ba(e){let t=e.file,n=t.content;if(!e.fields.length&&(e.schema_name===`text`||za(e.schema_name)!==null))return t.exists?D`<details class="ct-raw">
          <summary>${Va(t)}</summary>
          ${Ra(t)}
        </details>`:D``;if(!t.exists)return e.fields.length?D`<table class="ct-check">
          <tr><th>${M(`Field`)}</th><th>${M(`Expected`)}</th></tr>
          ${e.fields.map(e=>D`<tr>
              <td class="jmono">${e.name}</td>
              <td class="jmono jdim">${e.type}${e.required?O:D` <i>${M(`optional`)}</i>`}</td>
            </tr>`)}
        </table>`:D``;let r=typeof n==`object`&&n&&!Array.isArray(n)?n:null,i=e.fields.map(e=>{let t=D``,n;if(r){let i=e.name in r;n=i?r[e.name]:void 0,t=i?Fa(e.type,n)?Ma(!0,M(`passed`)):Ma(!1,M(`wrong type`),M(j`Expected ${e.type}`)):e.required?Ma(!1,M(`missing`),M(`A required field that is not in the file`)):D`<span class="fk none">${M(`absent (optional)`)}</span>`}return D`<tr>
      <td class="jmono">${e.name}</td>
      <td class="jmono jdim">${e.type}${e.required?O:D` <i>${M(`optional`)}</i>`}</td>
      <td>${La(n)}</td>
      <td>${t}</td>
    </tr>`}),a=r?Object.keys(r).filter(t=>!e.fields.some(e=>e.name===t)):[];return D`<table class="ct-check">
      <tr><th>${M(`Field`)}</th><th>${M(`Expected`)}</th><th>${M(`In the file`)}</th><th>${M(`Check`)}</th></tr>
      ${i}
      ${a.map(e=>D`<tr>
          <td class="jmono">${e}</td><td class="jdim">${M(`not in the schema`)}</td><td>${La(r?.[e])}</td>
          <td><span class="fk warn" title=${M(`Not in the schema`)}>${M(`extra field`)}</span></td>
        </tr>`)}
    </table>
    ${r?O:D`<div class="meta note">${M(`Not a JSON object`)}</div>`}
    <details class="ct-raw">
      <summary>${Va(t)}</summary>
      ${Ra(t)}
    </details>`}var Va=e=>H(M(`Whole file`),`${e.size??0} B`,e.mtime?M(j`written ${Mr(e.mtime,!0)}`):``,e.truncated?M(`truncated`):``);function Ha(e){let t=za(e.schema_name),n=e.schema_name===`text`||t===`str`?M(`text`):t??e.schema_name;return D`<b class="jmono" title=${e.schema_ref||e.schema_name}>${n}</b>`}function Ua(e){let t=e.schema_ref||e.schema_name;if(e.schema_name===`text`)return M(`text file`);let n=za(e.schema_name);return n===`str`?D`<span title=${t}>${M(`text (JSON string)`)}</span>`:n?D`<span title=${t}>${M(j`JSON value of type ${n}`)}</span>`:M(D`JSON object, schema ${Ha(e)}`)}function Wa(e){let t=e.validators??[];if(!t.length)return null;let n=(e.errors??[]).join(`
`),r=t=>e.status===`valid`?Ma(!0,M(`passed`)):n.includes(t)?Ma(!1,M(`failed checks`)):O;return D`${t.map((e,t)=>D`${t?`, `:``}<span class="jmono">${e}</span> ${r(e)}`)}`}function Ga(e,t){let n=Ua(e),r=Wa(e);return D`<dl class="conds">
    ${(t===`output`?[[M(`Format`),n],...r?[[M(`Other checks`),r,M(`Checks beyond the schema (validators)`)]]:[],[M(`Must be written during the task`),e.fresh?M(`yes`):M(`no`),e.fresh?M(`A file from before the task does not count`):M(`A file from before the task counts`)]]:[[M(`Format`),n],...r?[[M(`Other checks`),r,M(`Checks beyond the schema (validators)`)]]:[],[M(`Check time`),M(`when the task starts`)],[M(`Required`),e.required?M(`yes`):M(`no`)]]).map(([e,t,n])=>D`<dt>${e}</dt><dd title=${n??``}>${t}</dd>`)}
  </dl>`}var Ka=w`
  .ct-chip { display: inline-block; padding: 1px 10px; border-radius: var(--radius-pill); font-size: 11.5px; background: var(--raise); color: var(--text-2); white-space: nowrap; }
  .ct-chip b { margin-left: 4px; }
  /* a checked file's status: tinted by its tone, passed quiet with its ✓ in an outline */
  .ct-chip[data-tone] { background: var(--tone-bg); color: var(--tone); }
  .ct-chip[data-tone='done'] { background: none; box-shadow: inset 0 0 0 1px var(--line2); color: var(--text-2); }
`,qa=w`
  ${Ka}
  .ct-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ct-lead { margin: 2px 0 8px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 6px; }
  .conds { display: grid; grid-template-columns: max-content 1fr; gap: 2px 14px; margin: 2px 0 10px; font-size: 12px; }
  .conds dt { color: var(--text-muted); }
  .conds dd { margin: 0; color: var(--text-2); }
  /* sized to its content, so the check mark sits next to the value it judges; a long value wraps */
  .ct-check { width: auto; max-width: 100%; border-collapse: collapse; }
  .ct-check th { text-align: left; font-size: 11.5px; color: var(--text-muted);
    font-weight: 600; padding: 4px 20px 4px 0; border-bottom: 1px solid var(--line); }
  .ct-check td { padding: 5px 20px 5px 0; border: 0; border-bottom: 1px solid var(--line); vertical-align: baseline; font-size: 12.5px; }
  .ct-check th:last-child, .ct-check td:last-child { padding-right: 0; }
  .ct-check td:nth-child(3) { overflow-wrap: anywhere; }
  .ct-check tr:last-child td { border-bottom: 0; }
  .ct-check td:first-child { white-space: nowrap; font-weight: 600; }
  .ct-check td:last-child { white-space: nowrap; }
  .ct-check i { font-style: normal; color: var(--text-muted); font-size: 11px; margin-left: 4px; }
  .fk { font-size: 12px; }
  .fk.ok { color: var(--text-2); }
  .fk.ok > [aria-hidden] { color: var(--status-done); font-weight: 700; }
  .fk.bad { color: var(--status-failed); font-weight: 600; }
  .fk.warn { color: var(--status-attention); }
  .fk.none { color: var(--text-muted); }
  .js { color: var(--code-string); }
  .jn { color: var(--code-number); }
  .note { margin-top: 6px; }
  .ct-raw { margin-top: 8px; }
  .ct-raw > summary { cursor: pointer; color: var(--text-muted); font-size: 12px; }
  .ct-err { color: var(--status-failed); white-space: pre-wrap; }
  .ct-fields { border-collapse: collapse; width: 100%; }
  .ct-fields td { padding: 2px 10px 2px 0; border: 0; font-size: 12px; }
  .ct-in { display: flex; align-items: center; gap: 10px; padding: 5px 4px; border-top: 1px solid var(--line); }
  h4 { margin: 8px 0 6px; font-size: 12px; color: var(--text-2); font-weight: 600; }
  .io-card { border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; background: var(--raise); }
  .io-hd { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
  .io-from { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; margin: -2px 0 8px; }
  .io-hd .ct-path { flex: 1; }
  .io-card.one .io-hd { margin-bottom: 2px; }
`,Ja=new Set([`instructions`,`schema`,`agent`]),Ya=e=>{let t=e.split(`/`).filter(Boolean);return t.length>2?`…/${t.slice(-2).join(`/`)}`:e},Xa=class extends k{constructor(...e){super(...e),this.definition=null,this.memory=`definition`,this.open=new ni(`definition:open`),this.source=new ni(`definition:source`)}static{this.styles=[I,wn,En,Ka,w`
      :host { display: block; }
      .ct-in { display: flex; align-items: center; gap: 10px; padding: 5px 4px; border-top: 1px solid var(--line); }
      .df { border-top: 1px solid var(--line); }
      .df > summary { cursor: pointer; padding: 6px 2px; display: flex; gap: 10px; align-items: center; list-style: none; }
      .df > summary::-webkit-details-marker { display: none; }
      .df > summary::before { content: '▸'; color: var(--text-muted); width: 10px; transition: transform 0.15s; }
      .df[open] > summary::before { transform: rotate(90deg); }
      .py-sig { font-family: var(--mono); font-size: 14px; padding: 10px 14px; background: var(--well); border: 1px solid var(--line);
        border-radius: 8px; overflow-x: auto; white-space: pre; }
      .py-where { margin: 6px 2px 12px; font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); overflow-wrap: anywhere; }
      .py-doc { margin: 0 0 12px; padding: 8px 12px; border-left: 3px solid var(--line2); color: var(--text-2); white-space: pre-wrap; line-height: 1.6; }
      .src { display: grid; grid-template-columns: auto minmax(0, 1fr); background: var(--well); border: 1px solid var(--line);
        border-radius: 8px; font-family: var(--mono); font-size: 12px; line-height: 1.55; max-height: 520px; overflow: auto; }
      .src pre { margin: 0; padding: 10px 12px; white-space: pre; }
      .src .ln { color: var(--text-muted); text-align: right; user-select: none; border-right: 1px solid var(--line); opacity: 0.7; }
    `]}willUpdate(e){e.has(`memory`)&&(this.open=new ni(`${this.memory}:open`),this.source=new ni(`${this.memory}:source`))}render(){let e=this.definition;if(!e)return D`<div class="blank"><span class="ic" aria-hidden="true">⌘</span><b>${M(`No definition`)}</b></div>`;if(e.executor===`python`)return this.python(e);let t=e.plugin_dirs||[],n=[[M(`Role`),e.role||M(`none`,{id:`none`,desc:`An empty value`})],[t.length>1?M(`Plugin directories`):M(`Plugin directory`),t.length?D`${t.map((e,t)=>D`${t?`, `:``}<span class="jmono" title=${e}>${Ya(e)}</span>`)}`:M(`none`,{id:`none`,desc:`An empty value`})],[M(`Parameters`),e.params||M(`none`,{id:`none`,desc:`An empty value`})],[M(`Output`,{id:`definition-output`,desc:`The output file of a task definition`}),e.output||M(`none`,{id:`none`,desc:`An empty value`})],...(e.validators||[]).length?[[M(`Other checks`),(e.validators||[]).join(`, `)]]:[]],r=Array.isArray(e.declared)?e.declared:[],i=t=>t.part===`agent`&&!!e.role&&t.path.replace(/^.*\//,``)===`${e.role}.md`,a=[...e.files||[]].sort((e,t)=>Number(i(t))-Number(i(e)));return D`<div class="drv-facts" style="margin-bottom:10px">${n.map(([e,t])=>D`<span><i>${e}</i>${t}</span>`)}</div>
      ${r.length?D`<h4 class="sect-h">${M(`Checked files`)}</h4>
            ${r.map(e=>D`<div class="ct-in">
                <span class="ct-chip">${e.io}</span><span class="jmono">${e.path}</span>
                <span class="meta" title=${M(`The schema the file is checked against`)}>${M(j`Schema ${e.schema}`)}</span>
              </div>`)}`:O}
      ${a.length?D`<h4 class="sect-h">${M(`Files`)}</h4>${a.map(t=>this.file(t,i(t),!!e.role))}`:D`<div class="meta">${M(D`No files | defined in Python code (<code>TaskAdapter</code>)`)}</div>`}`}python(e){let t=(e.files||[]).find(e=>e.part===`source`),n=e.line??1,r=t?t.text.replace(/\n$/,``).split(`
`).length:0,i=[[M(`Parameters`),e.params&&e.params!==`none`?e.params:M(`none`,{id:`none`,desc:`An empty value`})],[M(`Output`,{id:`definition-output`,desc:`The output file of a task definition`}),e.output&&e.output!==`none`?e.output:M(`none`,{id:`none`,desc:`An empty value`})],...(e.validators||[]).length?[[M(`Other checks`),(e.validators||[]).join(`, `)]]:[]];return D`${e.signature?D`<div class="py-sig hl">${wr(_r(`def ${e.signature}`,`python`))}</div>`:O}
      <div class="py-where">
        ${e.function??e.kind}${e.file?D` | <span title=${e.file}>${e.file.replace(/^.*\//,``)}${e.line?`:${e.line}`:``}</span>`:O}
      </div>
      ${e.doc?D`<div class="py-doc">${e.doc}</div>`:O}
      <div class="drv-facts" style="margin-bottom:12px">${i.map(([e,t])=>D`<span><i>${e}</i>${t}</span>`)}</div>
      ${t?D`<h4 class="sect-h">${M(`Source`)}</h4>
            <div class="src">
              <pre class="ln">${Array.from({length:r},(e,t)=>n+t).join(`
`)}</pre>
              <pre class="hl">${wr(_r(t.text.replace(/\n$/,``),`python`))}</pre>
            </div>`:O}`}file(e,t=!1,n=!1){let r=`${e.part}|${e.path}`,i=/\.md$/i.test(e.path),a=e.part===`instructions`,o=!i||this.source.has(r),s=e.part===`agent`&&n?t:Ja.has(e.part);return D`<details class="df" ?open=${this.open.has(r)||s&&!this.open.has(`closed:${r}`)} @toggle=${e=>{let t=e.target.open;this.open.set(r,t),this.open.set(`closed:${r}`,!t)}}>
      <summary>
        <span class="tag">${e.part}</span><span class="jmono">${e.path}</span>
        ${t?D`<span class="ct-chip">${M(`Role of this kind`)}</span>`:O}
        ${i?D`<button type="button" class="df-tog" @click=${e=>{e.preventDefault(),this.source.set(r,!this.source.has(r)),this.requestUpdate()}}>${M(o?`Show rendered`:`Show source`)}</button>`:O}
      </summary>
      ${o?D`<pre class="df-text"><code class="hl">${wr(a?Vr(e.text):_r(e.text,e.path))}</code></pre>`:wr(Sr(e.text,a?Hr:void 0))}
    </details>`}};V([R({attribute:!1})],Xa.prototype,`definition`,void 0),V([R()],Xa.prototype,`memory`,void 0),Xa=V([L(`ca-definition`),N()],Xa);var Za=6e3,Qa=[`wheel`,`touchstart`,`pointerdown`,`keydown`],$a=class{constructor(e){this.id=e,this.el=null,this.frame=0,this.restoring=!1,this.cancel=()=>{if(cancelAnimationFrame(this.frame),this.frame=0,this.restoring){this.restoring=!1;for(let e of Qa)this.el?.removeEventListener(e,this.cancel)}},this.onScroll=()=>{!this.restoring&&this.el&&ei(this.id,Math.round(this.el.scrollTop))}}attach(e){this.el!==e&&(this.detach(),this.el=e,e.addEventListener(`scroll`,this.onScroll,{passive:!0}))}detach(){this.cancel(),this.el?.removeEventListener(`scroll`,this.onScroll),this.el=null}restore(){let e=this.el;if(!e)return;this.cancel();let t=$r(this.id)??0;if(t<=0){e.scrollTop=0;return}let n=performance.now()+Za;this.restoring=!0;for(let t of Qa)e.addEventListener(t,this.cancel,{passive:!0,once:!0});let r=()=>{let i=e.scrollHeight-e.clientHeight;if(e.scrollTop=Math.min(t,i),i>=t||performance.now()>n)return this.cancel();this.frame=requestAnimationFrame(r)};r()}reset(){this.cancel(),this.el&&(this.el.scrollTop=0)}},eo=class{constructor(e,t){this.host=e,this.opts=t,e.addController(this)}hostConnected(){let e=this.opts.locale();tn(rn(e)?e:an())}hostUpdated(){let e=this.opts.locale();e!==this.seen&&(this.seen=e,rn(e)&&e!==en()&&tn(e)),this.opts.pageWide()&&(document.documentElement.lang=en()),this.host.lang=en()}},to=class{constructor(e,t){this.onKey=t,this.listener=e=>{let t=e.composedPath()[0];t instanceof HTMLElement&&t.matches(`input, select, textarea`)||e.metaKey||e.ctrlKey||e.altKey||this.onKey(e)},e.addController(this)}hostConnected(){document.addEventListener(`keydown`,this.listener)}hostDisconnected(){document.removeEventListener(`keydown`,this.listener)}},no=class{constructor(e,t){this.host=e,this.opts=t,this.light=v(),this.stop=null,e.addController(this)}get choice(){let e=this.opts.theme();return f(e)?e:g()}get shown(){return p(this.choice,this.light)}get system(){return p(`system`,this.light)}hostConnected(){this.apply();let e=globalThis.matchMedia?.(`(prefers-color-scheme: light)`);if(!e)return;let t=e=>{this.light=e.matches,this.host.requestUpdate()};e.addEventListener(`change`,t),this.stop=()=>e.removeEventListener(`change`,t)}hostDisconnected(){this.stop?.(),this.stop=null}hostUpdated(){this.apply()}apply(){let e=this.shown;this.host.getAttribute(`data-ca-theme`)!==e&&this.host.setAttribute(`data-ca-theme`,e),this.opts.pageWide()&&document.documentElement.getAttribute(`data-ca-theme`)!==e&&document.documentElement.setAttribute(`data-ca-theme`,e)}};function ro(e){switch(e){case`done`:return M(`done`,{id:`outcome-done`,desc:`The status of a task: done`});case`recovered`:return M(`done after retrying`);case`failed`:return M(`failed`);case`not_started`:return M(`not started`);case`running`:return M(`running`);case`waiting`:return M(`waiting`);case`skipped`:return M(`skipped`)}}var io=(e,t)=>e===`waiting`&&!t?M(`not run`):ro(e);function J(e,t){switch(e){case`done`:return M(j`${t} done`);case`recovered`:return M(j`${t} done after retrying`);case`failed`:return M(j`${t} failed`);case`not_started`:return M(j`${t} not started`);case`running`:return M(j`${t} running`);case`waiting`:return M(j`${t} waiting`);case`skipped`:return M(j`${t} skipped`);case`not_run`:return M(j`${t} not run`)}}function Y(e,t){return e?Da(e)?ao(e,t):M(j`unknown (${e})`):`—`}function ao(e,t){switch(e){case`completed`:return M(`done`,{id:`stop-completed`,desc:`How an attempt ended: completed`});case`skipped`:return M(`skipped`);case`invalid_input`:{let e=new Set(ha(t).map(e=>e.problem));return e.size===1&&e.has(`missing`)?M(`not started (input missing)`):e.size===1&&e.has(`checks`)?M(`not started (input failed checks)`):M(`not started (input missing or failed checks)`)}case`invalid_output`:return M(`failed checks`);case`timeout`:return M(`timed out`);case`max_turns`:return M(`turn limit reached`);case`budget`:return M(`cost limit reached`);case`context_budget`:return M(`context limit reached`);case`stalled`:return M(`stalled (no output)`);case`auth_failed`:return M(`authentication failed`);case`api_error`:return M(`API error`);case`rate_limited`:return M(`rate limited`);case`refused`:return M(`refused by the model`);case`aborted`:return M(`aborted`);case`denied`:return M(`permission denied`);case`error`:return M(`error`);case`no_output`:return M(`ended without a result`);case`launch_failed`:return M(`could not start the agent`);case`credential_mismatch`:return M(`wrong identity used`)}}var oo=e=>M(j`Attempt ${(e??0)+1}`);function so(e){let t=ji(e),n=e.map((e,n)=>t[n]?H(oo(e.attempt),M(`resumed run`)):oo(e.attempt));return n.map((t,r)=>n.indexOf(t)===n.lastIndexOf(t)?t:H(t,Mr(e[r]?.ts)))}function co(e){return e<=0?``:M(e===1?`1 correction`:j`${e} corrections`)}var lo=e=>M(j`Pass ${e}`),uo=e=>M(e<=1?`1 pass`:j`up to ${e} passes`),fo=e=>M(e<=1?`1 pass`:j`${e} passes`),po=e=>e.map(([e,t])=>M(e<=1?j`1 pass: ${t}`:j`${e} passes: ${t}`)).join(` | `),mo=()=>M(`loop`),ho=e=>e?e===`ambient`?M(`default`):e:``,go=e=>e===`ambient`?M(`local credentials (ambient)`):``,_o=e=>e.model||e.route||`—`;function vo(e,t){if(!e||e.length<2)return``;let n=e.map((t,n)=>n<e.length-1?M(j`${_o(t)} (${Y(t.stop)})`):_o(t)).join(` → `);return t==null?n:`${n} | ${P(t)}`}var yo=e=>e==null?`—`:`${Math.round(e)}%`;function bo(e){if(!e||e===`allowed`)return``;let t=e.split(`,`);return t.some(e=>[`rejected`,`exhausted`,`quota`,`blocked`].includes(e))?M(`limit reached`):t.every(e=>[`allowed_warning`,`warning`].includes(e))?M(`near the limit`):M(j`unknown (${e})`)}function xo(e,t=Date.now()){let n=Date.parse(e??``);if(Number.isNaN(n))return``;if(n<=t)return M(`reset`);let r=(n-t)/36e5,i=r>=48?M(j`${Math.floor(r/24)}d ${Math.floor(r%24)}h`):P((n-t)/1e3);return M(j`resets in ${i}`)}var So=e=>H(M(j`weekly ${yo(e.seven_day_pct)}`),M(j`5-hour ${yo(e.five_hour_pct)}`));function Co(e){let t=[e.seven_day_resets_at?M(j`Weekly usage ${yo(e.seven_day_pct)} (resets ${Mr(e.seven_day_resets_at,!0)})`):M(j`Weekly usage ${yo(e.seven_day_pct)}`),e.five_hour_resets_at?M(j`5-hour usage ${yo(e.five_hour_pct)} (resets ${Mr(e.five_hour_resets_at,!0)})`):M(j`5-hour usage ${yo(e.five_hour_pct)}`),M(j`Reported ${Mr(e.observed_at,!0)}`)],n=bo(e.status);return n&&t.push(M(j`Status: ${n}`)),t.join(`
`)}var wo=e=>H(So(e),ho(e.credential));function To(e){let t=e[0];if(!t)return``;let n=e.length-1;return n?H(wo(t.last),M(n===1?`1 more account`:j`${n} more accounts`)):So(t.last)}var Eo=e=>e.map(e=>e.credential?`${ho(e.credential)}\n${Co(e.last)}`:Co(e.last)).join(`

`),Do=(e,t)=>e.ready?pa(e.journal):t.quota??[];function Oo(e,t,n=Zi(e.journal,e.plan)){let r=na(t),i=e.ready?oa(e.journal)?.cost:t.cost_usd,a=i==null?``:zr(i),o=To(Do(e,t)),s=H(r==null?``:M(j`took ${P(r)}`),a,o,t.running?M(`running`):``);if(!e.ready)return s;let c=n.counts;return H(M(j`${c.doneTotal} of ${c.total} tasks done`),s)}function ko({tries:e,notStarted:t}){return H(M(e===1?`1 attempt`:j`${e} attempts`),t?J(`not_started`,t):``)}un(`cae-segmented`,or);function Ao(e,t){let n=U(e),r=q(e.reason,t).slice(0,110);return e.stop===`invalid_input`?[`attention`,M(j`${n}: not started`),r]:Ai(e)?[`failed`,M(j`${n}: ${Y(e.stop)}`),r]:(e.hops||[]).length>1?[`agent`,M(j`${n}: model switch`),vo(e.hops,e.wall_s).slice(0,110)]:[`done`,M(j`${n}: done`),H(P(e.wall_s),e.model)]}var jo={done:`✓`,failed:`✕`,attention:`◌`,running:`●`,agent:`✦`},Mo=5200,No=class extends k{constructor(...e){super(...e),this.toasts=[],this.next=0}static{this.styles=[I,w`
      :host { position: fixed; right: 18px; bottom: 18px; display: flex; flex-direction: column; gap: 8px; z-index: 60; pointer-events: none; }
      .toast { pointer-events: auto; min-width: 240px; max-width: 380px; padding: 10px 14px; border-radius: 11px;
        background: var(--panel2); border: 1px solid var(--line2); box-shadow: 0 18px 40px color-mix(in srgb, var(--shadow) 60%, transparent);
        display: flex; gap: 10px; align-items: flex-start; animation: toast-in 0.35s var(--ease) both; }
      .toast.out { animation: toast-out 0.35s var(--ease) both; }
      .ti { font-size: 16px; line-height: 1.2; }
      b { display: block; font-size: 12.5px; }
      span.sub { font-size: 11.5px; color: var(--text-muted); }
      .ti { color: var(--text-muted); }
      .toast[data-tone] .ti { color: var(--tone); }
      .toast[data-tone='failed'], .toast[data-tone='attention'] { border-color: color-mix(in srgb, var(--tone) 50%, var(--line2)); }
      .agent .ti { color: var(--agent); }
    `]}show(e,t,n=``){let r={id:this.next++,kind:e,title:t,sub:n,out:!1};this.toasts=[...this.toasts,r].slice(-4),setTimeout(()=>{this.toasts=this.toasts.map(e=>e.id===r.id?{...e,out:!0}:e),setTimeout(()=>this.toasts=this.toasts.filter(e=>e.id!==r.id),400)},Mo)}render(){return D`<div aria-live="polite" style="display:contents">
      ${B(this.toasts,e=>e.id,e=>D`<div class="toast ${e.kind===`agent`?`agent`:``} ${e.out?`out`:``}" data-tone=${e.kind===`agent`?O:e.kind}>
          <span class="ti" aria-hidden="true">${jo[e.kind]}</span>
          <div><b>${e.title}</b>${e.sub?D`<span class="sub">${e.sub}</span>`:O}</div>
        </div>`)}
    </div>`}};V([z()],No.prototype,`toasts`,void 0),No=V([L(`ca-toasts`)],No);var Po=w`
  :host { display: flex; flex-direction: column; height: 100%; min-height: 0; font: 13px/1.5 var(--sans); color: var(--text);
    background: var(--backdrop); }
  header { flex: none; display: flex; gap: 14px; align-items: center; padding: 10px 18px; border-bottom: 1px solid var(--line);
    background: color-mix(in srgb, var(--bg) 75%, transparent); backdrop-filter: blur(10px); position: relative; z-index: 20; }
  .brand { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; letter-spacing: 0.02em; }
  .brand svg { width: 22px; height: 22px; }
  .logo-core { fill: var(--accent); transform-origin: 12px 12px; }
  .logo-ring { stroke: var(--accent); opacity: 0.5; transform-origin: 12px 12px; }
  :host([live]) .logo-core { animation: core-beat 1.8s var(--ease) infinite; }
  :host([live]) .logo-ring { animation: turn 7s linear infinite; }
  .runbtn { display: flex; align-items: center; gap: 10px; min-width: 0; max-width: 52vw; cursor: pointer; padding: 6px 13px;
    border-radius: 999px; background: var(--panel); border: 1px solid var(--line); color: var(--text); transition: border-color 0.2s, background 0.2s; }
  .runbtn:hover { border-color: var(--line2); background: var(--panel2); }
  .rn { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: none; max-width: 40%; }
  .rs { color: var(--text-muted); font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chev { color: var(--text-muted); }
  ca-run-picker { inset-inline-start: 110px; }
  .hdr-right { margin-left: auto; display: flex; align-items: center; gap: 12px; min-width: 0; }
  .nowline { font-size: 12px; color: var(--text-2); white-space: nowrap; overflow: hidden; max-width: 40vw;
    display: inline-flex; align-items: center; gap: 4px; }
  .clock { font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); }
  .langs { --cae-segmented-radius: 999px; --cae-segmented-height: auto; --cae-segmented-padding: 2px 9px; --cae-segmented-font-size: 11px;
    --cae-segmented-divider: 0; --cae-segmented-hover: var(--text-2); }
  .live-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--status-running); display: inline-block; animation: breathe 1.8s ease-in-out infinite; }
  .live-dot.off { background: var(--line2); animation: none; box-shadow: none; }

  .bar { flex: none; display: flex; gap: 8px; padding: 8px 18px; border-top: 1px solid var(--line); align-items: center; flex-wrap: wrap; }
  .bar select, .bar input { background: var(--panel); color: var(--text); border: 1px solid var(--line); border-radius: 8px;
    padding: 5px 9px; outline: none; font: inherit; font-size: 12px; }
  .bar input:focus, .bar select:focus { border-color: var(--focus); box-shadow: 0 0 0 calc(var(--focus-width) - 2px) var(--focus); }

  main { border-top: 1px solid var(--line); flex: 1 1 auto; min-height: 0; overflow: auto; padding: 16px 18px 48px; }
  main.stream { display: flex; flex-direction: column; overflow: hidden; padding-bottom: 16px; }
  @media (max-width: 760px) {
    header { flex-wrap: wrap; gap: 8px; padding: 8px 12px; }
    .runbtn { max-width: calc(100vw - 130px); }
    .hdr-right { width: 100%; margin-left: 0; }
    .nowline { max-width: none; flex: 1; }
    nav { padding: 4px 8px 0; }
    main { padding: 12px 12px 40px; }
  }
`,Fo=()=>[{id:`overview`,label:M(`Overview`),icon:`◎`},{id:`tasks`,label:M(`Tasks`,{id:`tab-tasks`,desc:`Tab: the list of tasks`}),icon:`≡`},{id:`journal`,label:M(`History`),icon:`▤`,tip:`journal.jsonl`},{id:`outputs`,label:M(`Outputs`),icon:`▣`},{id:`definitions`,label:M(`Definitions`),icon:`⌘`},{id:`procs`,label:M(`Processes`),icon:`⚙`},{id:`stream`,label:M(`Task detail`),icon:`✦`}];function Io(e){return[...Fo().map(e=>({...e,panel:!1})),...e.map(e=>({id:`panel:${e.name}`,label:e.title||e.name,icon:e.icon||`▤`,tip:e.description?M(j`${e.description} (custom view)`):M(`Custom view`),panel:!0}))]}function Lo(e,t,n,r){return D`<nav>
    ${e.map((i,a)=>{let o=n(i.id);return D`${i.panel&&!e[a-1]?.panel?D`<span class="tab-sep" title=${M(`Custom views`)}></span>`:O}
        <button type="button" class="tab ${i.panel?`panel-tab`:``} ${i.id===t?`sel`:``}" title=${i.tip??O}
          @click=${()=>r(i.id)}>
          <span class="tab-ic" aria-hidden="true">${i.icon}</span>${i.label}${o&&o[0]!==``?D`<span class="badge" data-tone=${sn(o[1])}>${o[0]}</span>`:O}
        </button>`})}
    <span class="tab-ind init"></span>
    <span class="tabhint meta" role="note" aria-label=${M(`Keyboard shortcuts`)}
      ><span aria-hidden="true"><span class="kbd">1</span>–<span class="kbd">${Math.min(9,e.length)}</span> ${M(`Tabs`)} |
        <span class="kbd">r</span> ${M(`Runs`)} | <span class="kbd">/</span> ${M(`Filter`)}</span></span
    >
  </nav>`}function Ro(e){let t=e.querySelector(`.tab.sel`),n=e.querySelector(`.tab-ind`);t&&n&&(n.style.left=`${t.offsetLeft+10}px`,n.style.width=`${Math.max(12,t.offsetWidth-20)}px`,n.classList.contains(`init`)&&requestAnimationFrame(()=>n.classList.remove(`init`)))}var zo=w`
  nav { flex: none; display: flex; gap: 2px; padding: 6px 18px 0; position: relative; overflow-x: auto; scrollbar-width: none; align-items: center; }
  nav::-webkit-scrollbar { display: none; }
  .tab { position: relative; background: none; border: none; padding: 8px 14px 11px; color: var(--text-muted); cursor: pointer;
    font-weight: 500; white-space: nowrap; transition: color 0.2s; }
  .tab:hover { color: var(--text-2); }
  .tab.sel { color: var(--text); }
  .tab-ic { opacity: 0.55; margin-right: 6px; font-size: 12px; }
  .tab.sel .tab-ic { opacity: 1; color: var(--accent); }
  .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--text-2); font-variant-numeric: tabular-nums; }
  .badge[data-tone] { background: var(--tone-bg); color: var(--tone); }
  .tab-sep { width: 1px; height: 18px; background: var(--line2); margin: 0 8px 3px; flex: none; align-self: center; }
  .tab-ind { position: absolute; bottom: 0; left: 0; width: 0; height: 2px; border-radius: 2px;
    background: var(--accent); transition: left 0.3s var(--ease), width 0.3s var(--ease); }
  .tab-ind.init { transition: none; }
  .tabhint { margin-left: auto; padding-left: 12px; white-space: nowrap; }
`;function Bo(e,t,n){return n.key?D`<button type="button" class="taskchip" title=${n.key} @click=${t=>{t.stopPropagation(),A(e,`ca-open-task`,{key:n.key,...G(n)?{view:`output`}:{}})}}>${t}</button>`:D`<span class="taskchip">${t}</span>`}var Vo=e=>D`<div class="brand">
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle class="logo-ring" cx="12" cy="12" r="9.5" fill="none" stroke-width="1.5" stroke-dasharray="4 3" />
      <circle class="logo-core" cx="12" cy="12" r="4" />
    </svg>
    <span>${e}</span>
  </div>`,Ho=(e,t)=>D`<span class="nowline">${t.length?M(D`Running ${t.slice(0,3).map(t=>Bo(e,U(t),{key:t.key}))}${t.length>3?D` <span>+${t.length-3}</span>`:O}`):O}</span>`,Uo=e=>D`<span title=${M(e?`Connected to the monitor server`:`Not connected to the monitor server`)}
    ><span class="live-dot ${e?``:`off`}"></span><span class="sr">${M(e?`Connected to the monitor server`:`Not connected to the monitor server`)}</span></span
  >`;un(`cae-count`,Or),un(`cae-elapsed`,kr);var Wo=class extends k{constructor(...e){super(...e),this.procs=null}static{this.styles=[I,w`
      :host { display: block; }
      .ptree2 { font-family: var(--mono); font-size: 11.5px; max-height: 220px; overflow: auto; }
      .pt-n { display: flex; gap: 10px; align-items: center; padding: 3px 6px 3px calc(6px + var(--d) * 18px); border-radius: 6px; position: relative; }
      .pt-n:hover { background: color-mix(in srgb, var(--text) 4%, transparent); }
      .pt-n::before { content: ''; position: absolute; left: calc(var(--d) * 18px - 8px); top: 0; bottom: 50%; width: 8px;
        border-left: 1px solid var(--line2); border-bottom: 1px solid var(--line2); }
      .pt-n.root::before { display: none; }
      .pt-pid { color: var(--text-muted); min-width: 58px; }
      .pt-cmd { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; color: var(--text-2); }
      .pt-n.llm .pt-cmd { color: var(--text); }
      .pt-n.llm .pt-pid { box-shadow: inset 2px 0 0 color-mix(in srgb, var(--agent) 70%, transparent); padding-left: 6px; }
      .pt-age { color: var(--text-muted); }
    `]}render(){let e=this.procs?.tree[0];return e?D`<div class="ptree2">${this.node(e,0)}</div>`:D`<div class="meta">${M(`No running processes`)}</div>`}node(e,t){let n=e.full_cmd||e.cmd||``,r=(e.cmd||n).split(` `).slice(0,3).join(` `);return D`<div class="pt-n ${/\b(claude|omp)\b/.test(n)?`llm`:``} ${t?``:`root`}" style="--d:${t}" title=${n}>
        <span class="pt-pid">${e.pid}</span>
        <span class="pt-cmd">${e.key?D`<b>${U(e)}</b> `:O}${r.length>70?`${r.slice(0,70)}…`:r}</span>
        <cae-elapsed class="pt-age" .since=${hn.at(`p:${e.pid}`,e.age_s)}></cae-elapsed>
      </div>
      ${(e.children??[]).map(e=>this.node(e,t+1))}`}};V([R({attribute:!1})],Wo.prototype,`procs`,void 0),Wo=V([L(`ca-proc-tree`),N()],Wo);function Go(e){let t=e.filter(K),n=t.filter(G),r=t.filter(e=>!G(e)),i=e=>e.reduce((e,t)=>e+(t.wall_s||0),0),a=e=>[...new Set(e.map(e=>e.key))],o=e=>a(e).length,s=Bi(e),c=t.filter(e=>(e.rounds||1)>1),l=t.filter(e=>(e.hops||[]).length>1);return{attempts:t.length,python:n.length,launches:r.length,bad:t.filter(e=>!e.ok).length,launchWall:i(r),pythonWall:i(n),retries:s.length,retriedTasks:o(s),retriedKeys:a(s),fixupKeys:a(c),fixups:c.reduce((e,t)=>e+(t.rounds||1)-1,0),fixupTasks:o(c),switches:l.reduce((e,t)=>e+(t.hops||[]).length-1,0),switchTasks:o(l)}}function Ko(e){let t=!1,n=!1,r=!1;for(let i of e){if(i.outcome!==`not_started`)continue;let e=i.attempts[i.attempts.length-1],a=e?.stop===`invalid_input`?ha(e.reason):[];a.some(e=>e.problem===`missing`)&&(t=!0),a.some(e=>e.problem===`checks`)&&(n=!0),!a.length&&i.cause&&(r=!0)}return Fr(r?M(`Earlier task failed`):``,t?M(`Input missing`):``,n?M(`Input failed checks`):``)}var qo=()=>globalThis.matchMedia?.(`(prefers-reduced-motion: reduce)`).matches??!1,Jo=class extends k{constructor(...e){super(...e),this.journal=[],this.plan={nodes:[],groups:[]},this.prev=new Map,this.changed=[]}static{this.styles=[I,w`
      :host { display: block; }
      .kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
      @media (max-width: 1150px) { .kpis { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
      @media (max-width: 700px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      /* Neutral by default: the number is emphasised by size and weight. A tile whose subject is a problem
         (above 0) takes its status: the number, the mark before the label and a thin edge. */
      .kpi { position: relative; background: color-mix(in srgb, var(--text) 2.5%, transparent); border: 1px solid var(--line);
        border-radius: 11px; padding: 12px 14px; overflow: hidden; }
      .kpi::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--edge, transparent); }
      .k { font-size: 12px; font-weight: 600; color: var(--text-muted); }
      .v { font-size: 28px; font-weight: 700; line-height: 1.15; margin-top: 6px; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; color: var(--text); }
      .s { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; }
      .a { font-size: 11.5px; margin-top: 4px; }
      .kpi[data-tone] { --edge: var(--tone); }
      .kpi[data-tone] .v, .kpi[data-tone] .k::before { color: var(--tone); }
      .k[data-mark]::before { display: inline-block; }
    `]}history(e){return()=>A(this,`ca-navigate`,{tab:`journal`,stop:e})}show(e,t,n){let r=e.length===1?e[0]:void 0,i=r?this.journal.find(e=>e.key===r):void 0;return r?{label:i?U(i):r,run:()=>A(this,`ca-open-task`,{key:r})}:{label:n,run:this.history(t)}}tiles(){let e=Go(this.journal),{outcomes:t,counts:n}=Zi(this.journal,this.plan),r=[{text:J(`done`,n.doneTotal),tone:`neutral`},{text:n.skipped?J(`skipped`,n.skipped):``,tone:`neutral`},{text:n.failed?J(`failed`,n.failed):``,tone:wa(n.failed,`failed`)},{text:n.not_started?J(`not_started`,n.not_started):``,tone:wa(n.not_started,`attention`)}];return[{id:`tasks`,tone:`neutral`,label:M(`Tasks`,{id:`tasks`,desc:`A count of tasks`}),value:n.total,sub:[[]],parts:r},{id:`attempts`,tone:`neutral`,label:M(`Attempts`),value:e.attempts,sub:[Fr(e.launches===1?M(`1 agent session`):M(j`${e.launches} agent sessions`),e.python===1?M(`1 Python task attempt`):M(j`${e.python} Python task attempts`))],tip:M(`Attempts that ran, retries included (journal.jsonl)`)},...this.spendTiles(),{id:`bad`,tone:wa(e.bad,`failed`),label:M(`Failed attempts`),value:e.bad,sub:[e.bad?[]:[M(`All attempts passed`)]],...e.bad?{action:{label:M(`Failed attempts in history`),run:this.history(`bad`)}}:{}},{id:`notstarted`,tone:wa(n.not_started,`attention`),label:M(`Not started`),value:n.not_started,sub:[n.not_started?Ko(t.values()):[M(`All tasks started`)]],...n.not_started?{action:{label:M(`Not-started tasks in history`),run:this.history(`invalid_input`)}}:{}},{id:`wall`,tone:`neutral`,label:M(`Agent session time`),value:P(e.launchWall),sub:[[M(j`Python tasks: ${P(e.pythonWall)}`)]],tip:M(`Sum over all agent sessions, including ones running at once`)},{id:`retry`,tone:`neutral`,label:M(`Retries`),value:e.retries,sub:[[e.retries?e.retriedTasks===1?M(`1 task retried`):M(j`${e.retriedTasks} tasks retried`):M(`No retries`)]],tip:M(`Attempts after a failed attempt, each in a new agent session (RetryingRunner)`),...e.retries?{action:this.show(e.retriedKeys,`retried`,M(`Retried tasks in history`))}:{}},{id:`ct`,tone:`neutral`,label:M(`Corrections`),value:e.fixups,sub:[[e.fixups?e.fixupTasks===1?M(`1 task with corrections`):M(j`${e.fixupTasks} tasks with corrections`):M(`No corrections`)]],tip:M(`More rounds in the same agent session after the output failed checks (rounds)`),...e.fixups?{action:this.show(e.fixupKeys,`fixup`,M(`Attempts with corrections in history`))}:{}},{id:`fo`,tone:`neutral`,label:M(`Model switches`),value:e.switches,sub:[[e.switches?e.switchTasks===1?M(`1 task with model switches`):M(j`${e.switchTasks} tasks with model switches`):M(`No model switches`)]],tip:M(`To the next model after a failure such as a rate limit, an error or a timeout (Router hops)`)}]}spendTiles(){let e=oa(this.journal);if(!e)return[];let t=la(this.journal)[0];return[{id:`cost`,tone:`neutral`,label:M(`Cost`),value:zr(e.cost),sub:t&&t.share!==null?[[M(j`Highest cost: ${t.kind}`)],Fr(zr(t.spend.cost),M(j`${Math.round(t.share*100)}% of the total`))]:[[]],tip:M(`Reported by the coding agent`)},{id:`tokens`,tone:`neutral`,label:M(`Tokens`),value:W(ia(e)),sub:[Fr(M(j`${W(e.input)} input`),M(j`${W(e.output)} output`),M(j`${W(e.cache_read+e.cache_creation)} cache`))],tip:H(M(j`${W(e.cache_read)} cache read`),M(j`${W(e.cache_creation)} cache write`),e.calls===1?M(`1 API call`):M(j`${e.calls} API calls`))}]}render(){let e=this.tiles();this.changed=[];for(let t of e)typeof t.value==`number`&&((this.prev.get(t.id)??0)!==t.value&&this.changed.push(t.id),this.prev.set(t.id,t.value));return D`<div class="kpis">${e.map(e=>this.tile(e))}</div>`}tile(e){return D`<div class="kpi" data-tone=${sn(e.tone)} data-id=${e.id} title=${e.tip??O}>
      <div class="k words" data-mark=${Dn(e.tone)??O}>${e.label}</div>
      <div class="v">${typeof e.value==`number`?D`<cae-count .value=${e.value}></cae-count>`:e.value}</div>
      ${e.parts?D`<div class="s words">${Vn(e.parts)}</div>`:e.sub.map(e=>D`<div class="s words">${Vn(e)}</div>`)}
      ${e.action?D`<div class="a words"><a class="lnk" href="#" @click=${t=>{t.preventDefault(),e.action?.run()}}>${e.action.label}</a></div>`:O}
    </div>`}updated(){if(!qo())for(let e of this.changed)this.renderRoot.querySelector(`.kpi[data-id="${e}"]`)?.animate([{transform:`scale(1)`},{transform:`scale(1.04)`,boxShadow:`0 0 0 1px var(--line2)`,offset:.35},{transform:`scale(1)`}],{duration:700,easing:`cubic-bezier(.2,.8,.2,1)`})}};V([R({attribute:!1})],Jo.prototype,`journal`,void 0),V([R({attribute:!1})],Jo.prototype,`plan`,void 0),Jo=V([L(`ca-kpis`),N()],Jo);var Yo=[`input`,`cache_read`,`cache_creation`,`output`],Xo=class extends k{constructor(...e){super(...e),this.journal=[],this.top=5}static{this.styles=[I,Bn,w`
      :host { display: block; }
      .kinds { display: grid; grid-template-columns: minmax(90px, max-content) minmax(0, 1fr) max-content max-content; gap: 8px 14px; align-items: center; }
      .kind { font-family: var(--mono); font-size: 12px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .bar { display: flex; height: 12px; border-radius: 4px; overflow: hidden; background: var(--track); }
      .bar i { display: block; height: 100%; }
      .num { font-variant-numeric: tabular-nums; text-align: right; font-size: 12px; white-space: nowrap; }
      .share { color: var(--text-muted); min-width: 3.5em; }
      .seg-input { background: var(--tok-input); }
      .seg-cache_read { background: var(--tok-cache-read); }
      .seg-cache_creation { background: var(--tok-cache-write); }
      .seg-output { background: var(--tok-output); }
      .legend { margin-top: 10px; }
      h4 { margin: 16px 0 6px; font-size: 12px; color: var(--text-2); font-weight: 600; }
      .top { display: grid; grid-template-columns: minmax(160px, max-content) 64px 64px 40px; column-gap: 24px; row-gap: 4px; align-items: baseline; }
      .top a { font-family: var(--mono); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    `]}partLabel(e){switch(e){case`input`:return M(`input`);case`cache_read`:return M(`cache read`);case`cache_creation`:return M(`cache write`);case`output`:return M(`output`)}}bar(e,t){let n=ia(e),r=t?100*n/t:0;return D`<div class="bar" title=${H(...Yo.map(t=>`${this.partLabel(t)} ${W(e[t])}`))} style="width:${Math.max(r,.5).toFixed(2)}%">
      ${Yo.map(t=>e[t]&&n?D`<i class="seg-${t}" style="width:${(100*e[t]/n).toFixed(2)}%"></i>`:O)}
    </div>`}render(){if(!oa(this.journal))return D`<div class="meta">${M(`No tokens reported`)}</div>`;let e=la(this.journal),t=Math.max(1,...e.map(e=>ia(e.spend))),n=ca(this.journal).slice(0,this.top);return D`<div class="kinds">
        ${B(e,e=>e.id,e=>D`<span class="kind" title=${e.id}>${e.id}</span>${this.bar(e.spend,t)}
            <span class="num">${H(W(ia(e.spend)),zr(e.spend.cost))}</span>
            <span class="num share">${e.share===null?``:`${Math.round(e.share*100)}%`}</span>`)}
      </div>
      ${zn(Yo.map(e=>({label:this.partLabel(e),cls:`seg-${e}`})))}
      <h4>${M(`Most expensive tasks`)}</h4>
      <div class="top">
        ${n.map(e=>D`<a class="lnk" href="#" title=${e.id} @click=${t=>{t.preventDefault(),A(this,`ca-open-task`,{key:e.id})}}>${U(e)}</a>
            <span class="num">${W(ia(e.spend))}</span>
            <span class="num">${zr(e.spend.cost)}</span>
            <span class="num share">${e.share===null?``:M(j`${Math.round(e.share*100)}%`)}</span>`)}
      </div>`}};V([R({attribute:!1})],Xo.prototype,`journal`,void 0),V([R({type:Number})],Xo.prototype,`top`,void 0),Xo=V([L(`ca-spend-breakdown`),N()],Xo);var Zo=class extends k{static{this.styles=[I,w`
      :host { display: block; }
      .rows { display: grid; grid-template-columns: max-content minmax(0, 1fr) max-content max-content; gap: 10px 14px; align-items: center; }
      .name { font-size: 12px; color: var(--text-2); white-space: nowrap; }
      .bar { position: relative; height: 12px; border-radius: 4px; background: var(--track); overflow: hidden; }
      .bar i { position: absolute; top: 0; bottom: 0; }
      /* usage measures, it does not judge: neutral, attention from 80% (the number says it too) */
      .bar .before { left: 0; background: var(--meter); opacity: 0.45; }
      .bar .during { background: var(--meter); }
      .bar.hot .during, .bar.full .during, .bar.hot .before, .bar.full .before { background: var(--status-attention); }
      .val.hot b, .val.full b { color: var(--status-attention); }
      .val { font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
      .val b { color: var(--text); }
      .reset { font-size: 11.5px; color: var(--text-muted); white-space: nowrap; }
      .status { margin-top: 8px; }
      .acct { padding: 10px 0; border-top: 1px solid var(--line); }
      .acct:first-child { border-top: 0; padding-top: 0; }
      .acct-h { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; font-size: 12px; }
      .acct-h i { font-style: normal; color: var(--text-muted); font-size: 11px; }
      .acct-h b { font-family: var(--mono); color: var(--text); font-weight: 600; }
    `]}constructor(){super(),this.journal=[],new mn(this)}row(e,t,n,r){let i=n[`${e}_pct`],a=r[`${e}_pct`];if(i==null&&a==null)return O;let o=Math.max(0,Math.min(100,i??a??0)),s=Math.max(o,Math.min(100,a??o)),c=r[`${e}_resets_at`],l=s>=100?`full`:s>=80?`hot`:``;return D`<span class="name">${t}</span>
      <span class="bar ${l}" title=${`${yo(i)} → ${yo(a)}`}>
        <i class="before" style="width:${o}%"></i>
        <i class="during" style="left:${o}%;width:${s-o}%"></i>
      </span>
      <span class="val ${l}">${yo(i)} → <b>${yo(a)}</b></span>
      <span class="reset" title=${c?Mr(c,!0):``}>${xo(c)}</span>`}render(){let e=pa(this.journal);return e.length?D`${e.map(e=>{let t=bo(e.last.status);return D`<div class="acct">
        <div class="acct-h"><i>${M(`Identity`)}</i><b>${ho(e.credential)||`—`}</b>${t?kn({text:t,tone:`attention`,title:e.last.status,mark:null}):O}</div>
        <div class="rows">
          ${this.row(`seven_day`,M(`Weekly usage`),e.first,e.last)} ${this.row(`five_hour`,M(`5-hour usage`),e.first,e.last)}
        </div>
      </div>`})}`:O}};V([R({attribute:!1})],Zo.prototype,`journal`,void 0),Zo=V([L(`ca-quota`),N()],Zo);var Qo=Nn(class extends Pn{constructor(){super(...arguments),this.key=O}render(e,t){return this.key=e,t}update(e,[t,n]){return t!==this.key&&(nr(e),this.key=t),n}}),$o=e=>e?`⚙`:`✦`;function X(e,t,n){return Un($o(e),t,{cls:n??`k-ic ${e?``:`llm`}`})}var es=w`
  .k-ic { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; margin-right: 7px;
    font-size: var(--font-size-sm); background: var(--raise); color: var(--text-muted); flex: none; }
  .k-ic.llm { background: var(--agent-bg); color: var(--agent); }
`,ts=(e,t,n)=>{let r=e.get(t);r?r.push(n):e.set(t,[n])},ns=(e,t)=>`${e}\u0000${t}`;function rs(e,t,n){let r=new Set(e),i=new Map(e.map(e=>[e,[]]));for(let[e,n]of t)e!==n&&r.has(e)&&r.has(n)&&!i.get(e)?.includes(n)&&i.get(e)?.push(n);let a=new Set,o=new Map;for(let t of e){if(o.has(t))continue;o.set(t,1);let e=[[t,0]];for(;e.length;){let t=e[e.length-1],n=i.get(t[0])??[];if(t[1]<n.length){let r=n[t[1]++],i=o.get(r);i===1?a.add(ns(t[0],r)):i||(o.set(r,1),e.push([r,0]))}else o.set(t[0],2),e.pop()}}let s=new Map(e.map(e=>[e,[]])),c=new Map(e.map(e=>[e,[]]));for(let[e,t]of i)for(let n of t)a.has(ns(e,n))||(s.get(e)?.push(n),c.get(n)?.push(e));let l=new Map(e.map(e=>[e,c.get(e)?.length??0])),u=e.filter(e=>!l.get(e)),d=new Map;for(let e=u.shift();e!==void 0;e=u.shift()){d.set(e,n.get(e)??Math.max(0,...(c.get(e)??[]).map(e=>(d.get(e)??0)+1)));for(let t of s.get(e)??[])l.set(t,(l.get(t)??0)-1),l.get(t)||u.push(t)}return d}function is(e,t,n,r){let i=0,a=new Map;for(let[e,i]of t){let t=r.get(e);t!==void 0&&ts(a,t,[n.get(e)??0,n.get(i)??0])}for(let e of a.values())for(let t=0;t<e.length;t++)for(let n=t+1;n<e.length;n++){let[r,a]=e[t],[o,s]=e[n];(r-o)*(a-s)<0&&i++}return e.length?i:0}var Z=e=>e.startsWith(`~`);function as(e,t,n){let r=new Map;e.forEach((e,t)=>e.forEach(e=>r.set(e,t)));let i=new Map,a=new Map;for(let[e,n]of t)ts(a,e,n),ts(i,n,e);let o=new Map,s=e=>e.forEach((e,t)=>o.set(e,t)),c=e.map(e=>[...e]);c.forEach(s);let l=()=>is(c,t,o,r),u=c.map(e=>[...e]),d=l(),f=(e,t)=>{let r=new Map;for(let n of e){let e=(t.get(n)??[]).map(e=>o.get(e)).filter(e=>e!==void 0);r.set(n,e.length?e.reduce((e,t)=>e+t,0)/e.length:o.get(n)??0)}let i=e=>r.get(e)??0;if(!n)return[...e].sort((e,t)=>i(e)-i(t)||(o.get(e)??0)-(o.get(t)??0));let a=e.filter(e=>!Z(e)),s=e.filter(Z).sort((e,t)=>i(e)-i(t)||(o.get(e)??0)-(o.get(t)??0)),c=[],l=0;for(let e of a){for(;l<s.length&&i(s[l])<i(e);)c.push(s[l++]);c.push(e)}return[...c,...s.slice(l)]};for(let e=0;e<4;e++){let t=e%2==0,n=t?c.map((e,t)=>t).slice(1):c.map((e,t)=>t).reverse().slice(1);for(let e of n){let n=f(c[e],t?i:a);c[e]=n,s(n)}let r=l();r<d&&(d=r,u=c.map(e=>[...e]))}return l()<=d?c:u}var os=`loop:`,ss=e=>typeof e==`string`;function cs(e){let t=e.flow;if(!Array.isArray(t))return[];let n=[];for(let e of t){let t=e;if(!t||typeof t!=`object`||!ss(t.function))break;let r=(Array.isArray(t.loops)?t.loops:[]).filter(e=>!!e&&typeof e.line==`number`);n.push({function:t.function,file:ss(t.file)?t.file:``,line:typeof t.line==`number`?t.line:0,loops:r.map(e=>e.line),passes:r.map(e=>typeof e.pass==`number`&&e.pass>=1?e.pass:1)})}return n}function ls(e){let t=e.flow_calls;return!Array.isArray(t)||t.length===0?null:new Map(t.filter(e=>e&&ss(e.id)&&ss(e.function)).map(e=>[e.id,e]))}var us=new WeakMap;function ds(e){let t=us.get(e);if(t)return t;let n=e.nodes.map(e=>{let t=cs(e),n=e.created_from;return{n:e,frames:t,path:t.map(e=>e.function),from:Array.isArray(n)?n.filter(ss):[],call:ss(e.flow_call)?e.flow_call:``}}),r=new Map;for(let t of e.nodes)t.unit&&!r.has(t.unit)&&r.set(t.unit,r.size);let i={tasks:n,byKey:new Map(n.map(e=>[e.n.key,e])),calls:ls(e),unitRank:r,labels:new Map(e.groups.map(e=>[e.id,e.label]))};return us.set(e,i),i}var fs=(e,t)=>t.every((t,n)=>e[n]===t),ps=e=>e.slice(e.lastIndexOf(`.`)+1)||e,ms=(e,t)=>t>0?e.frames[t-1]?.loops??[]:[],hs=(e,t)=>t>0?e.frames[t-1]?.passes??[]:[];function gs(e,t){for(let n=0;n<Math.max(e.length,t.length);n++){let r=(e[n]??0)-(t[n]??0);if(r)return r}return 0}var _s=e=>e.map((t,n)=>`${os}${e.slice(0,n+1).join(`.`)}`);function vs(e,t){let n=ms(e,t),r=n.length?`@${n.join(`.`)}`:``;if(e.path.length<=t)return{id:`kind:${e.n.group}${r}`,type:`kind`,name:e.n.group,loops:n};let i=e.path[t];return{id:`flow:${i}${r}`,type:`flow`,name:i,loops:n}}function ys(e,t,n){if(!e.call)return{id:`>${t}`,own:!1};let r=e.call.split(`.`),i=r.map((e,t)=>r.slice(0,t+1).join(`.`)),a=0,o=0;if(n)for(let r=1;r<i.length;r++){let s=n.get(i[r])?.function,c=s===void 0?-1:e.frames.findIndex((e,t)=>t>o&&e.function===s);if(c<0||c>t)break;a=r,o=c}else a=Math.min(t,i.length-1),o=a;let s=i[a];return o===t?{id:s,own:!0}:{id:`${s}>${t}`,own:!1}}var bs={failed:5,running:4,blocked:3,pending:2,skipped:1,done:0},xs=e=>e.reduce((e,t)=>bs[t.state]>bs[e]?t.state:e,`done`),Ss=e=>e.reduce((e,t)=>bs[t]>bs[e]?t:e,`done`);function Cs(e){let t=e.filter(G).length;return t===0?`agent`:t===e.length?`python`:`mixed`}var ws={running:`running`,returned:`done`,raised:`failed`,closed:`failed`},Ts=e=>e?.state===`raised`||e?.state===`closed`;function Es(e,t){let n=e.map(e=>e.n);return{key:(n.find(e=>e.state===`running`)??n[n.length-1]??{key:``}).key,unit:t,state:xs(n),count:n.length,keys:n.map(e=>e.key)}}function Ds(e){let t=new Map,n=[];for(let r of e)r.n.unit?ts(t,r.n.unit,r):n.push(Es([r],``));return{byUnit:new Map([...t].map(([e,t])=>[e,Es(t,e)])),single:n}}function Os(e,t,n){let r=new Map;for(let i of e){let{id:e,own:a}=ys(i,t,n);(r.get(e)??r.set(e,{id:e,own:a,tasks:[],unit:``}).get(e))?.tasks.push(i)}for(let e of r.values()){let t=new Set(e.tasks.map(e=>e.n.unit||``));e.unit=t.size===1?[...t][0]:``}return[...r.values()]}function ks(e,t,n,r){let i=(e,t)=>{let i=e.map(e=>e.own?r?.get(e.id):void 0),a=e.map((e,t)=>{let n=i[t],r=xs(e.tasks.map(e=>e.n));return n&&ws[n.state]?Ss([ws[n.state],r]):r}),o=e.flatMap(e=>e.tasks),s=o.map(e=>e.n.key),c=e.find((e,t)=>a[t]===`running`)??e[e.length-1],l=i.find(Ts),u={key:c?.id??``,unit:t,state:Ss(a),count:s.length,keys:s,flow:n,counts:As(o)};return l?{...u,error:l.error??``}:u},a=new Map,o=[],s=Os(e,t,r);for(let e of s)e.unit?ts(a,e.unit,e):o.push(i([e],``));let c=r?s.filter(e=>e.own&&Ts(r.get(e.id))).length:0;return{byUnit:new Map([...a].map(([e,t])=>[e,i(t,e)])),single:o,calls:s.length,errors:c}}function As(e){let t={total:e.length,done:0,failed:0,running:0,pending:0,skipped:0,blocked:0};for(let n of e)t[n.n.state]+=1;return t}function js(e,t){let n=new Map;for(let r of e){let e=r.n.unit||``,i=n.get(e);(!i||gs(hs(r,t),i)>0)&&n.set(e,hs(r,t))}return e.filter(e=>gs(hs(e,t),n.get(e.n.unit||``)??[])===0)}function Ms(e,t){let n=new Map;for(let r of e){let e=r.n.unit||``;(n.get(e)??n.set(e,new Set).get(e))?.add(hs(r,t).join(`.`))}return new Map([...n].map(([e,t])=>[e,t.size]))}var Ns=(e,t)=>t&&t>1?{...e,passes:t}:e;function Ps(e,t,n,r=!1){let i=ds(e),a=t.length,o=i.tasks.filter(e=>fs(e.path,t)),s=new Map,c=new Map;for(let e of o){let t=vs(e,a);(s.get(t.id)??s.set(t.id,{...t,tasks:[]}).get(t.id))?.tasks.push(e),c.set(e.n.key,t.id)}let l=new Map,u=new Map,d=new Map,f=new Map;for(let e of s.values()){let t=_s(e.loops),n=t[t.length-1]??null;t.forEach((e,n)=>f.set(e,t[n-1]??null)),n&&d.set(e.id,n);let r=n?js(e.tasks,a):e.tasks;u.set(e.id,r);let o=e.type===`kind`?Ds(r):ks(r,a,e.name,i.calls);if(n){let t=Ms(e.tasks,a);o.byUnit=new Map([...o.byUnit].map(([e,n])=>[e,Ns(n,t.get(e))]))}l.set(e.id,o)}let p=[...new Set([...l.values()].flatMap(e=>[...e.byUnit.keys()]))].sort((e,t)=>(i.unitRank.get(e)??0)-(i.unitRank.get(t)??0)),m=new Map,h=new Map;for(let e of s.values()){let t=_s(e.loops);for(let n of e.tasks){let e=hs(n,a);t.forEach((t,r)=>{m.set(t,Math.max(m.get(t)??1,e[r]??1));let i=h.get(t)??h.set(t,new Map).get(t),a=n.n.unit||``;(i?.get(a)??i?.set(a,new Set).get(a))?.add(e.slice(0,r+1).join(`.`))})}}let g=e=>{let t=[],n=e.startsWith(`loop:`)?e:d.get(e)??null;for(;n;)t.push(n),n=f.get(n)??null;return t},_=(e,t)=>{let n=g(e);if(t===``)return n[n.length-1]??e;let r=n.indexOf(t);return r<0?void 0:r===0?e:n[r-1]},v=(e,t)=>g(e).find(e=>g(t).includes(e))??``,y=e=>e.startsWith(`stub:`)?``:d.get(e)??``,b=new Set,x=new Map,ee=new Map,S=e=>{let n=0;for(;n<a&&e.path[n]===t[n];)n++;let r=vs(e,n);return{id:`stub:${n}:${r.id}`,label:r.type===`kind`?i.labels.get(r.name)??r.name:ps(r.name)}};for(let e of o){let t=c.get(e.n.key),n=(n,r)=>{let o=c.get(n);if(o===t){r===`after`&&b.add(t);return}if(o!==void 0){let s=i.byKey.get(n),c=ms(s,a),l=ms(e,a),u=0;for(;u<c.length&&c[u]===l[u];)u++;let d=gs(hs(s,a).slice(0,u),hs(e,a).slice(0,u))===0,f=`${o}\u0000${t}\u0000${r}`,p=x.get(f)??x.set(f,{from:o,to:t,type:r,tasks:new Set,samePass:!1}).get(f);p?.tasks.add(e.n.key),p&&d&&(p.samePass=!0);return}let s=i.byKey.get(n);if(!s)return;let l=S(s),u=`${l.id}\u0000${t}\u0000${r}`;(ee.get(u)??ee.set(u,{...l,to:t,type:r,tasks:new Set}).get(u))?.tasks.add(e.n.key)};for(let t of e.n.after??[])n(t,`after`);for(let t of e.from)n(t,`created`)}let C=[...x.values()].filter(e=>e.type===`after`||!x.has(`${e.from}\u0000${e.to}\u0000after`)),w=[...ee.values()].filter(e=>e.type===`after`||!ee.has(`${e.id}\u0000${e.to}\u0000after`)),te=[``,...f.keys()],ne=new Map(te.map(e=>[e,[]]));for(let e of s.keys())for(let t of te){let n=_(e,t);n!==void 0&&!ne.get(t)?.includes(n)&&ne.get(t)?.push(n)}let re=new Map;for(let e of te){let t=ne.get(e)??[],r=e===``?n?.layers:n?.boxes[e],i=new Map;r?.forEach((e,n)=>e.forEach(e=>t.includes(e)&&i.set(e,n)));let a=C.filter(t=>t.samePass&&v(t.from,t.to)===e).map(t=>[_(t.from,e),_(t.to,e)]);re.set(e,rs(t,a,i))}let ie=re.get(``),ae=[...new Set(w.map(e=>e.id))],oe=new Map;n?.layers.forEach((e,t)=>e.forEach(e=>oe.set(e,t)));let se=new Map(ae.map(e=>[e,oe.get(e)??Math.min(...w.filter(t=>t.id===e).map(e=>ie.get(_(e.to,``))??0))-1]));if([...se.values()].some(e=>e<0)){for(let[e,t]of ie)ie.set(e,t+1);for(let[e,t]of se)se.set(e,t+1)}for(let[e,t]of se)ie.set(e,t);let T=(e,t)=>re.get(e)?.get(t)??0,E=e=>Math.max(0,...re.get(e)?.values()??[]),ce=(e,t)=>{let n=v(e,t);return T(n,_(e,n))>=T(n,_(t,n))},le=C.map(e=>({from:e.from,to:e.to,tasks:e.tasks.size,type:e.type,back:ce(e.from,e.to)})),ue=new Map;for(let e of te){let t=((e===``?n?.layers:n?.boxes[e])??[]).flat(),r=[...e===``?[...ae]:[],...ne.get(e)??[]];r.sort((e,n)=>{let r=t.indexOf(e),i=t.indexOf(n);return(r<0?1/0:r)-(i<0?1/0:i)});let i=Array.from({length:E(e)+1},()=>[]);for(let t of r)i[T(e,t)]?.push(t);ue.set(e,i)}let de=[],fe=new Set,pe=(e,t,n,r)=>{let i=`~${e}|${t}|${n}|${r}`;return fe.has(i)||(fe.add(i),ue.get(e)?.[r]?.push(i)),{id:i,in:e}},me=(e,t,n,r)=>{let i=T(e,t),a=`~${e}|by:${t}|${n}|${r}|${i}`;return fe.has(a)||(fe.add(a),ue.get(e)?.[i]?.push(a)),{id:a,in:e}},he=(e,t,n)=>{let i=e.startsWith(`stub:`)?``:v(e,t),a=y(e),o=e,s=[{id:e,in:a}];for(;a!==i;){let e=f.get(a)??``;s.push({id:a,in:e}),T(a,o)<E(a)&&s.push(me(e,a,o,n)),o=a,a=e}let c=_(t,i);for(let e=T(i,o)+1;e<T(i,c);e++)s.push(pe(i,o,n,e));let l=g(t),u=l.slice(0,i===``?l.length:l.indexOf(i)).reverse(),d=`>${i}:${o}`,p=i;for(let e of u){let i=_(t,e);(T(e,i)>0||r)&&s.push(me(p,e,d,n)),s.push({id:e,in:p}),p=e}return s.push({id:t,in:p}),s};for(let e of le)e.back||de.push({from:e.from,to:e.to,type:e.type,steps:he(e.from,e.to,e.type)});for(let e of w)de.push({from:e.id,to:e.to,type:e.type,steps:he(e.id,e.to,e.type)});let ge={};for(let e of te){let t=[],r=new Map((ue.get(e)??[]).flatMap((e,t)=>e.map(e=>[e,t])));for(let n of de)for(let i=1;i<n.steps.length;i++){let a=n.steps[i-1],o=n.steps[i];a.in===e&&o.in===e&&r.get(a.id)!==r.get(o.id)&&t.push([a.id,o.id])}let i=e===``?!!n:!!n?.boxes[e];ge[e]=as(ue.get(e)??[],t,i).map(e=>{let t=e.filter(e=>e.includes(`|by:`));return e.filter(e=>!e.includes(`|by:`)).flatMap(e=>[e,...t.filter(t=>t.includes(`|by:${e}|`))])})}let _e=e=>e.map(e=>e.filter(e=>!Z(e))),ve=[...f.keys()].map(e=>{let t=new Map;for(let[n,r]of h.get(e)??[])n&&t.set(r.size,(t.get(r.size)??0)+1);return{id:e,loop:Number(e.slice(os.length).split(`.`).pop()),file:o[0]?.frames[a-1]?.file??``,parent:f.get(e)??null,passes:m.get(e)??1,spread:[...t].sort((e,t)=>e[0]-t[0]),layers:_e(ge[e]??[]).filter(e=>e.length)}}),ye=_e(ge[``]??[]).map(e=>e.filter(e=>!e.startsWith(`stub:`))),be=e=>{let t=l.get(e.id),n=t.byUnit.size>0;return{id:e.id,type:e.type,name:e.name,label:e.type===`kind`?i.labels.get(e.name)??e.name:ps(e.name),kinds:[...new Set(e.tasks.map(e=>e.n.kind))],executor:e.type===`flow`?null:Cs(e.tasks.map(e=>e.n)),box:d.get(e.id)??null,units:n?p.map(e=>t.byUnit.get(e)??null):[],single:t.single,inOrder:b.has(e.id),counts:As(u.get(e.id)??[]),calls:t.calls??0,errors:t.errors??0}},xe=new Map(ve.map(e=>[e.id,e])),Se=e=>e.flatMap(e=>e.startsWith(`loop:`)?Se((xe.get(e)?.layers??[]).flat()):[e]);return{graph:{path:[...t],nodes:Se(ye.flat()).map(e=>be(s.get(e))),layers:ye.filter(e=>e.length),boxes:ve,edges:le,stubs:w.map(e=>({id:e.id,label:e.label,to:e.to,tasks:e.tasks.size,type:e.type})),units:p,slots:ge,routes:de,order:{layers:_e(ge[``]??[]),boxes:Object.fromEntries(ve.map(e=>[e.id,_e(ge[e.id]??[])]))}},drafts:s,ix:i}}function Fs(e,t=[],n,r=!1){return Ps(e,t,n,r).graph}function Is(e){let t=ds(e),n=[],r=new Set;if(t.calls)for(let e of t.calls.values())(e.state===`raised`||e.state===`closed`)&&r.add(e.id);let i=e=>r.has(e)&&![...r].some(t=>t!==e&&t.startsWith(`${e}.`));for(;;){let e=null,r=!0,a=[];for(let i of t.tasks){if(!fs(i.path,n))continue;let t=vs(i,n.length);if(t.type===`kind`||e&&e.id!==t.id){r=!1;break}e=t,a.push(i)}let o=a.some(e=>i(ys(e,n.length,t.calls).id));if(!r||!e||o)return n;n.push(e.name)}}function Ls(e){let t=e[e.length-1];return t?.startsWith(`loop:`)?{path:e.slice(0,-1),loop:t}:{path:[...e],loop:null}}function Rs(e,t){let{path:n,loop:r}=Ls(t),i=ds(e),a=t=>!r||Fs(e,t).boxes.some(e=>e.id===r);if(i.tasks.some(e=>fs(e.path,n)))return a(n)?[...t]:null;let o=n[n.length-1];if(o===void 0)return null;let s=e=>{let t=new Map;for(let n of i.tasks)n.path.forEach((r,i)=>e(r)&&t.set(n.path.slice(0,i+1).join(`/`),n.path.slice(0,i+1)));return[...t.values()]},c=s(e=>e===o),l=c.length?c:s(e=>ps(e)===o),u=l.length===1?l[0]:null;return u&&a(u)?r?[...u,r]:u:null}function zs(e,t){if(e.length<=t.length)return null;let n=e.slice(0,-1);return n.length<=t.length?[]:n}var Bs={across:{gap:56,boxGap:40,sep:16,pointSep:12,pad:12,padEnd:24,margin:16},down:{gap:40,boxGap:32,sep:16,pointSep:12,pad:10,padEnd:24,margin:16}};function Vs(e,t,n){let r=[0];for(let n=1;n<e.length;n++)r.push(r[n-1]+t[n-1]);let i=[];e.forEach((e,t)=>{let a=n[t]??1;for(i.push({sum:a*(e-r[t]),w:a,n:1});i.length>1;){let e=i[i.length-1],t=i[i.length-2];if(t.sum/t.w<=e.sum/e.w)break;i.splice(-2,2,{sum:t.sum+e.sum,w:t.w+e.w,n:t.n+e.n})}});let a=[];for(let e of i)for(let t=0;t<e.n;t++)a.push(e.sum/e.w+r[a.length]);return a}function Hs(e,t,n=!1){let r=Bs[n?`down`:`across`],i=e=>n?e.h:e.w,a=e=>n?e.w:e.h,o=new Set(e.boxes.map(e=>e.id)),s=e=>t.get(`lbl:${e}`)??{w:0,h:0},c=e=>n?{u0:s(e).h+r.pad+r.gap/2,u1:r.pad,v0:r.pad,v1:r.padEnd,minU:0,minV:s(e).w+2*r.pad}:{u0:r.pad,u1:r.pad,v0:s(e).h+r.pad,v1:r.padEnd,minU:s(e).w+2*r.pad,minV:0},l=new Map,u=e=>{if(o.has(e))return l.get(e)??{u:0,v:0};if(Z(e))return{u:0,v:0};let n=t.get(e)??{w:0,h:0};return{u:i(n),v:a(n)}},d=new Map,f=new Map,p=e=>e===``?0:e.split(`.`).length,m=[``,...e.boxes.map(e=>e.id)].sort((e,t)=>p(t)-p(e)),h=(t,n)=>{let r=e.routes[t]?.steps??[],i=r[n];if(Z(i.id))return 0;if(!o.has(i.id))return u(i.id).v/2;let a=r[n-1]?.in===i.id?n-1:n+1,s=r[a];return c(i.id).v0+(d.get(i.id)?.top.get(s.id)??0)+h(t,a)};for(let t of m){let n=(e.slots[t]??[]).map(e=>[...e]);f.set(t,new Map(n.flatMap((e,t)=>e.map(e=>[e,t]))));let i=n.map(e=>Math.max(0,...e.map(e=>u(e).u))),a=t===``?r.gap:r.boxGap,s=[];i.forEach((e,t)=>s.push(t?s[t-1]+i[t-1]+a:0));let p=[];e.routes.forEach((e,n)=>e.steps.forEach((r,i)=>{let a=e.steps[i-1];i&&a&&a.in===t&&r.in===t&&f.get(t)?.get(a.id)!==f.get(t)?.get(r.id)&&p.push({a:a.id,b:r.id,oa:h(n,i-1),ob:h(n,i)})}));let m=(e,t)=>t===void 0?0:o.has(e)||o.has(t)||!(Z(e)||Z(t))?r.sep:r.pointSep,g=new Map;for(let e of n){let t=0;e.forEach((n,r)=>{g.set(n,t),t+=u(n).v+m(n,e[r+1])})}let _=(e,t)=>{let n=e.map(e=>{let n=t(e);return n.length?n.reduce((e,t)=>e+t,0)/n.length:g.get(e)??0}),r=e.map((t,n)=>u(t).v+m(t,e[n+1])),i=e.map((e,t)=>Z(e)?-1:t).filter(e=>e>=0),a=(e,t)=>r.slice(e,t).reduce((e,t)=>e+t,0),o=Vs(i.map(e=>n[e]),i.map((e,t)=>t+1<i.length?a(e,i[t+1]):0),i.map(()=>1));i.forEach((e,t)=>n[e]=o[t]),Vs(n,r,e.map(e=>Z(e)?1:1e6)).forEach((t,n)=>g.set(e[n],Math.round(t*100)/100))},v=(e,t)=>{let n=Z(e)?t:t.filter(e=>!Z(e.other));return(n.length?n:t).map(e=>e.at)},y=e=>v(e,p.filter(t=>t.b===e).map(e=>({other:e.a,at:(g.get(e.a)??0)+e.oa-e.ob}))),b=e=>v(e,p.filter(t=>t.a===e).map(e=>({other:e.b,at:(g.get(e.b)??0)+e.ob-e.oa})));for(let e=0;e<8;e++){let t=n.map((e,t)=>t);e%2&&t.reverse();for(let r of t)_(n[r],e%2?b:y)}for(let e of n)_(e,e=>[...y(e),...b(e)]);let x=g.size?Math.min(...g.values()):0;for(let[e,t]of g)g.set(e,t-x);let ee=(s[s.length-1]??0)+(i[i.length-1]??0),S=Math.max(0,...n.flat().map(e=>(g.get(e)??0)+u(e).v));if(d.set(t,{rows:n,start:s,width:i,top:g,u:ee,v:S}),t!==``){let e=c(t);l.set(t,{u:Math.max(e.u0+ee+e.u1,e.minU),v:Math.max(e.v0+S+e.v1,e.minV)})}}let g={},_=new Map,v=(e,t,r)=>n?{x:t,y:e,w:r.v,h:r.u}:{x:e,y:t,w:r.u,h:r.v},y=(e,t,n)=>{_.set(e,{u:t,v:n});let r=d.get(e);r.rows.forEach((e,i)=>e.forEach(e=>{if(Z(e))return;let a=t+r.start[i],s=n+(r.top.get(e)??0);if(g[e]=v(a,s,u(e)),o.has(e)){let t=c(e);y(e,a+t.u0,s+t.v0)}}))};y(``,r.margin,r.margin);let b=d.get(``),x=b.u+2*r.margin,ee=b.v+2*r.margin,S=(e,t)=>{let n=d.get(e),r=(_.get(e)??{u:0,v:0}).u+(n.start[t]??0);return[r,r+(n.width[t]??0)]},C=(e,t)=>f.get(e)?.get(t)??0,w=e=>e&&Z(e.id)?/\|by:([^|]*)\|/.exec(e.id)?.[1]??``:``,te=e.routes.map((e,t)=>{let i=n=>{let r=e.steps[n];return(_.get(r.in)??{u:0,v:0}).v+(d.get(r.in)?.top.get(r.id)??0)+h(t,n)},a=e.steps.map((t,a)=>{let o=e.steps[a-1],l=e.steps[a+1],[f,p]=S(t.in,C(t.in,t.id)),m=i(a);if(a===0)return{a:f+u(t.id).u,b:p,at:m};if(a===e.steps.length-1)return{a:f,b:f,at:m};if(Z(t.id)){let i=w(t);if(i&&o?.id===i)return{a:S(i,C(i,e.steps[a-2]?.id??``)+1)[0],b:p,at:m};if(i&&l?.id===i){let t=C(i,e.steps[a+2]?.id??``);return{a:f,b:t>0?S(i,t-1)[1]:(g[i]?n?g[i].y:g[i].x:f)+s(i).h+r.pad,at:m}}return{a:f,b:p,at:m}}let h=c(t.id),_=d.get(t.id);if(o?.in===t.id){if(w(l)===t.id){let e=S(t.id,C(t.id,o.id)+1)[0];return{a:e,b:e,at:i(a+1)}}return{a:f+h.u0+_.u,b:p,at:m}}if(w(o)===t.id){let e=S(t.id,C(t.id,l?.id??``))[0];return{a:e,b:e,at:i(a+1)}}return{a:f,b:f+h.u0,at:m}});return{from:e.from,to:e.to,type:e.type,runs:a}}),ne=e.boxes.flatMap(e=>{let t=d.get(e.id),n=_.get(e.id);if(!t||!n)return[];let r=e=>{let n=(e??[]).filter(e=>!Z(e)),r=null;for(let e of n){let n=u(e),i=(t.top.get(e)??0)+n.v;(!r||i>r.v)&&(r={u:n.u,v:i})}return r},i=t.rows.map((e,t)=>e.some(e=>!Z(e))?t:-1).filter(e=>e>=0),a=i[0]??0,o=i[i.length-1]??0,s=r(t.rows[o]),c=r(t.rows[a]);if(!s||!c)return[];let l=n.u+(t.start[o]??0)+(t.width[o]??0)/2,f=n.u+(t.start[a]??0)+(t.width[a]??0)/2;if(l-f<24){let e=Math.max(12,Math.min(28,Math.min(s.u,c.u)/4));l=(l+f)/2+e,f=l-2*e}return[{box:e.id,from:l,v0:n.v+s.v,to:f,v1:n.v+c.v,band:n.v+t.v+12}]});return{w:n?ee:x,h:n?x:ee,at:g,edges:te,returns:ne,down:n}}function Us(e){return e<=12?{cols:Math.max(1,e),size:12}:e<=100?{cols:10,size:10}:{cols:20,size:6}}var Ws=e=>e.units.filter(e=>e!==null).length+e.single.length>200;function Gs(e,t){return t.filter(t=>e[t]>0).map(t=>({state:t,n:e[t],pct:100*e[t]/Math.max(1,e.total)}))}function Ks(e,t,n,r){let{graph:i,drafts:a,ix:o}=Ps(e,t,r),s=i.boxes.find(e=>e.id===n);if(!s)return null;let c=t.length,l=s.id.slice(os.length).split(`.`).length-1,u=new Map(i.boxes.map(e=>[e.id,e])),d=new Map(i.nodes.map(e=>[e.id,e])),f=e=>hs(e,c).slice(l),p=e=>e.layers.flat().flatMap(e=>u.has(e)?p(u.get(e)):[e]),m=e=>p(e).flatMap(e=>a.get(e)?.tasks??[]),h=(e,t)=>e.length===t.length&&gs(e,t)===0,g=(e,t)=>{let n=t.length;return[...new Set(m(e).map(f).filter(e=>e.length>n&&gs(e.slice(0,n),t)===0).map(e=>e[n]))].sort((e,t)=>e-t).flatMap(n=>{let r=[...t,n],i=e.layers.flat().flatMap(e=>{let t=u.get(e);if(t){let e=g(t,r);return e.length?[{type:`loop`,box:t,kids:e}]:[]}let n=d.get(e);return n&&a.get(e)?.tasks.some(e=>h(f(e),r))?[{type:`node`,node:n,passes:r}]:[]});return i.length?[{type:`pass`,box:e,pass:n,kids:i}]:[]})},_=g(s,[]),v=[],y=e=>e.type===`node`?1:e.kids.reduce((e,t)=>e+y(t),0),b=e=>e.type===`node`?1:1+Math.max(0,...e.kids.map(b)),x=Math.max(1,..._.map(b)),ee=Array.from({length:x},()=>[]),S=(e,t)=>{let n=ee[t];if(e.type===`node`){n.push({type:`node`,node:e.node,passes:e.passes,span:1,rows:x-t}),v.push({node:e.node,passes:e.passes});return}n.push(e.type===`pass`?{type:`pass`,box:e.box,pass:e.pass,span:y(e),rows:1}:{type:`loop`,box:e.box,span:y(e),rows:1});for(let n of e.kids)S(n,t+1)};for(let e of _)S(e,0);let C=m(s),w=new Set(C.map(e=>e.n.unit||``)),te=[...i.units.filter(e=>w.has(e)),...w.has(``)?[``]:[]],ne=new Map;v.forEach((e,t)=>{for(let n of a.get(e.node.id)?.tasks??[])h(f(n),e.passes)&&ts(ne,`${t}\u0000${n.n.unit||``}`,n)});let re=(e,t,n)=>{let r=a.get(e.node.id);if(r.type===`kind`)return Es(t,n);let i=ks(t,c,r.name,o.calls);return n?i.byUnit.get(n)??i.single[0]??null:i.single[0]??null};return{box:s,columns:v,head:ee,rows:te.map(e=>{let t=v.map((t,n)=>{let r=ne.get(`${n}\u0000${e}`);return r?.length?re(t,r,e):null});return{unit:e,passes:new Set(C.filter(t=>(t.n.unit||``)===e).map(e=>hs(e,c).slice(0,l+1).join(`.`))).size,state:Ss(t.filter(e=>e!==null).map(e=>e.state)),cells:t}})}}function qs(e,t){let n=new Map(e.map((e,t)=>[e,t])),r=e=>t===`passes`?-e.passes:t===`state`?-bs[e.state]:0;return[...e].sort((e,t)=>r(e)-r(t)||(n.get(e)??0)-(n.get(t)??0))}function Js(e,t,n,r,i=!1,a=10){let o=(t,n)=>e[t]?.[n]===!0,s=t=>(e[t]??[]).findIndex(Boolean),c=t=>(e[t]??[]).lastIndexOf(!0),l=(t,n,r)=>{for(let i=t;i>=0&&i<e.length;i+=n)if(o(i,r))return i;return-1},u=t=>{let r=e[t]??[],i=-1;return r.forEach((e,t)=>e&&(i<0||Math.abs(t-n)<Math.abs(i-n))&&(i=t)),i<0?null:[t,i]};switch(r){case`ArrowRight`:case`ArrowLeft`:{let i=r===`ArrowRight`?1:-1;for(let r=n+i;r>=0&&r<(e[t]?.length??0);r+=i)if(o(t,r))return[t,r];return null}case`ArrowDown`:case`ArrowUp`:{let i=r===`ArrowDown`?1:-1,a=l(t+i,i,n);if(a>=0)return[a,n];for(let n=t+i;n>=0&&n<e.length;n+=i)if(s(n)>=0)return u(n);return null}case`Home`:{let n=i?e.findIndex(e=>e.some(Boolean)):t;return n<0||s(n)<0?null:[n,s(n)]}case`End`:{let n=t;if(i)for(n=e.length-1;n>=0&&c(n)<0;n--);return n<0||c(n)<0?null:[n,c(n)]}case`PageDown`:case`PageUp`:{let n=r===`PageDown`?1:-1,i=Math.max(0,Math.min(e.length-1,t+n*a));for(let e=i;e!==t;e-=n)if(s(e)>=0)return u(e);return null}default:return null}}function Ys(e,t,n,r){let i=new Map(e.nodes.map((e,t)=>[e.id,t])),a=[...new Set(e.edges.filter(e=>!e.back&&(n===`later`?e.from===t:e.to===t)).map(e=>n===`later`?e.to:e.from))],o=r(t);return a.sort((e,t)=>Math.abs(r(e)-o)-Math.abs(r(t)-o)||(i.get(e)??0)-(i.get(t)??0)),a[0]??null}function Xs(e,t=!1,n=3){let r=e=>Math.round(e*2)/2,i=(e,n)=>t?`${r(n)},${r(e)}`:`${r(e)},${r(n)}`,a=Math.max(0,Math.min(6,(e.from-e.to)/2,e.band-e.v0-n,e.band-e.v1-n));return[`M${i(e.from,e.v0+n)}`,`L${i(e.from,e.band-a)}`,`Q${i(e.from,e.band)} ${i(e.from-a,e.band)}`,`L${i(e.to+a,e.band)}`,`Q${i(e.to,e.band)} ${i(e.to,e.band-a)}`,`L${i(e.to,e.v1+n)}`].join(` `)}function Zs(e,t=!1){let n=e=>Math.round(e*2)/2,r=(e,r)=>t?`${n(r)},${n(e)}`:`${n(e)},${n(r)}`,i=e[0];if(!i)return``;let a=`M${r(i.a,i.at)}`;return e.forEach((t,n)=>{t.b!==t.a&&(a+=` L${r(t.b,t.at)}`);let i=e[n+1];if(!i)return;if(Math.abs(i.at-t.at)<.5){i.a!==t.b&&(a+=` L${r(i.a,i.at)}`);return}let o=(t.b+i.a)/2;a+=` C${r(o,t.at)} ${r(o,i.at)} ${r(i.a,i.at)}`}),a}var Qs=14,$s=(e,t,n)=>n<t?t:Math.min(n,Math.max(t,e));function ec(e,t){let n=Math.max(e.left,t.left),r=Math.max(e.top,t.top),i=Math.min(e.left+e.width,t.left+t.width),a=Math.min(e.top+e.height,t.top+t.height);return i>n&&a>r?{left:n,top:r,width:i-n,height:a-r}:null}function tc(e,t,n,r=e){let i=ec(r,t);if(!i)return{shown:!1,x:0,y:0,side:`right`,arrow:0,fits:!1};let{width:a,height:o}=n,s=t.left+8,c=t.top+8,l=t.left+t.width-8,u=t.top+t.height-8,d=e.left+e.width,f=e.top+e.height,p=i.top+i.height/2,m=i.left+i.width/2,h=$s(p-o/2,c,u-o),g=$s(m-a/2,s,l-a),_={right:l-(d+12)-a,left:e.left-12-a-s,below:u-(f+12)-o,above:e.top-12-o-c},v=[`right`,`left`,`below`,`above`],y=v.find(e=>_[e]>=0)??v.reduce((e,t)=>_[t]>_[e]?t:e),b,x;switch(y){case`right`:[b,x]=[$s(d+12,s,l-a),h];break;case`left`:[b,x]=[$s(e.left-12-a,s,l-a),h];break;case`below`:[b,x]=[g,$s(f+12,c,u-o)];break;case`above`:[b,x]=[g,$s(e.top-12-o,c,u-o)]}let ee=y===`right`||y===`left`?$s(p-x,Qs,o-Qs):$s(m-b,Qs,a-Qs);return{shown:!0,x:b,y:x,side:y,arrow:ee,fits:_[y]>=0}}var nc=(e,t,n=[])=>`${e}${n.length?`|${n.join(`.`)}`:``}#${t.unit||t.key}`;function rc(e,t,n){if(!n)return null;let r=n.indexOf(`#`);if(r<0){let t=e.nodes.find(e=>e.id===n);if(t)return{type:`node`,id:n,node:t};let r=e.boxes.find(e=>e.id===n);return r?{type:`box`,id:n,box:r}:null}let[i=``,a]=n.slice(0,r).split(`|`),o=n.slice(r+1),s=e=>!!e&&(e.unit?e.unit===o:e.key===o);if(a!==void 0){if(!t)return null;let e=t.columns.findIndex(e=>e.node.id===i&&e.passes.join(`.`)===a),r=t.columns[e],o=t.rows.map(t=>t.cells[e]).find(s);return r&&o?{type:`mark`,id:n,node:r.node,mark:o,passes:r.passes}:null}let c=e.nodes.find(e=>e.id===i),l=c?[...c.units,...c.single].find(s):void 0;return c&&l?{type:`mark`,id:n,node:c,mark:l,passes:[]}:null}function ic(e,t,n,r){if(e<=0||t<=0||n<=0)return{k:1,x:0,y:0,h:Math.max(0,t)};let i=Math.min(1,n/e),a=Math.min(t*i,r),o=Math.min(i,a/t);return{k:o,x:(n-e*o)/2,y:(a-t*o)/2,h:a}}function ac(e,t,n,r,i,a){let o=Math.min(a,Math.max(i,e.k*t)),s=o/e.k;return{k:o,x:n-(n-e.x)*s,y:r-(r-e.y)*s}}var oc=[`done`,`running`,`pending`,`failed`,`blocked`,`skipped`],sc=640,cc=.7,lc=360,uc=2.5,dc=4,fc=24,pc=150,mc=30,hc=8,gc=(e=14)=>D`<svg class="ic loop-ic" width=${e} height=${e} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
    <path d="M12.7,9.71 A5,5 0 1 1 11.21,4.17" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"></path>
    <path d="M12.44,5.2 L9.15,5.06 L11.73,2 z" fill="currentColor"></path>
  </svg>`,_c=()=>D`<svg class="ic in-ic" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
    <rect x="3.4" y="0.7" width="7.9" height="7.9" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.2"></rect>
    <path d="M0.7,3.6 V9.7 Q0.7,11.3 2.3,11.3 H8.4" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"></path>
  </svg>`,vc=e=>[...e.units,...e.single];function yc(e,t){let n=vc(e),r=e.units.length?Us(t):Us(n.length);return{cols:Math.min(r.cols,Math.max(1,n.length)),size:r.size,gap:r.size>=10?4:2}}var Q=class extends k{constructor(...e){super(...e),this.plan={nodes:[],groups:[]},this.journal=[],this.run=``,this.live=!1,this.layer=``,this.unit=``,this.sel=``,this.hover=null,this.asTable=!1,this.down=!1,this.lay=null,this.view={k:1,x:0,y:0},this.frameH=0,this.sort=`order`,this.scrollRow=0,this.missing=``,this.pressed=!1,this.cardRoom=0,this.announced=``,this.replacing=!1,this.auto=[],this.segments=[],this.graph={path:[],nodes:[],layers:[],boxes:[],edges:[],stubs:[],units:[],slots:{},routes:[],order:{layers:[],boxes:{}}},this.matrix=null,this.orders=new Map,this.byKey=new Map,this.waiters=new Map,this.active=new Map,this.cell=null,this.refocus=!1,this.cameFrom=``,this.layKey=``,this.layPath=``,this.fitK=1,this.moved=!1,this.pan=null,this.swallowClick=!1,this.quiet=!1,this.onTabToCard=e=>{if(e.key!==`Tab`||e.shiftKey||e.defaultPrevented)return;let t=this.anchorFocus(),n=this.renderRoot instanceof ShadowRoot?this.renderRoot.activeElement:null;if(!t||n!==t)return;let r=this.renderRoot.querySelector(`.insp button`);r&&(e.preventDefault(),r.focus())},this.onEscape=e=>{if(e.key!==`Escape`||e.defaultPrevented)return;if(this.sel){e.preventDefault(),this.select(``);return}let t=zs(this.segments,this.auto);t&&(e.preventDefault(),this.refocus=!0,this.cameFrom=this.segments[this.segments.length-1]??``,this.go(t))},this.onWheel=e=>{if(this.asTable||this.matrix||!(e.ctrlKey||e.metaKey))return;let t=this.renderRoot.querySelector(`.frame`);if(!t)return;e.preventDefault();let n=t.getBoundingClientRect();this.zoomBy(Math.exp(-e.deltaY*.0015),e.clientX-n.left,e.clientY-n.top)},this.onClickCapture=e=>{this.swallowClick&&(this.swallowClick=!1,e.stopPropagation(),e.preventDefault())}}static{this.styles=[I,es,Bn,w`
      :host { display: block; }

      /* One frame for every view of a layer: the graph, the table and a loop's passes. */
      .frame { position: relative; overflow: hidden; border-radius: 8px; background: var(--well); box-sizing: border-box; }
      .gframe { cursor: grab; touch-action: none; }
      .gframe.drag { cursor: grabbing; }
      .stage { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
      .gframe.down { touch-action: pan-y pinch-zoom; }
      /* A view's content fades in when the view changes; the frame stays. */
      .view { animation: view-in 0.1s var(--ease) both; }
      @keyframes view-in { from { opacity: 0; } }
      @media (prefers-reduced-motion: reduce) { .view { animation: none; } }
      .tools { display: flex; align-items: center; gap: 4px; justify-self: end; }
      .tools button { all: unset; cursor: pointer; min-width: 22px; height: 22px; padding: 0 7px; box-sizing: border-box; text-align: center;
        font-size: 11.5px; line-height: 22px; color: var(--text-2); border-radius: 6px; border: 1px solid var(--line); }
      .tools button:hover:not(:disabled) { color: var(--text); border-color: var(--line2); }
      .tools button:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
      .tools button:disabled { cursor: default; opacity: 0.4; }
      /* Graph | Table: the chosen one is raised, as the header's language switch. */
      .views { margin-left: 6px; }

      .dag { position: relative; }
      .dag.unplaced { visibility: hidden; }
      .dag > *, .box > .in > * { position: absolute; }
      .edges { left: 0; top: 0; pointer-events: none; overflow: visible; z-index: 0; }
      .edges path { fill: none; stroke: var(--line2); stroke-width: 1.5; }
      .edges path.created { stroke-dasharray: 5 4; }
      /* A loop's return to its next pass: dotted, lighter than the edges, under the box's nodes. */
      .edges path.ret, .legend svg path.ret { stroke: var(--text-2); stroke-width: 2; stroke-dasharray: 0.1 4; stroke-linecap: round; opacity: 0.8; }
      .edges path.ret-tip, .legend svg path.ret-head { fill: var(--text-2); stroke: none; opacity: 0.8; }
      .ic { display: block; flex: none; }
      .loop-ic { color: var(--text-2); }
      .in-ic { color: var(--text-muted); }
      .unset { visibility: hidden; }

      .stub { z-index: 1; font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); padding: 3px 9px;
        border-radius: 999px; border: 1px solid var(--line); background: var(--card); white-space: nowrap; }

      .box { z-index: 1; box-sizing: border-box; border-radius: 14px; border: 1px solid var(--line2); background: color-mix(in srgb, var(--text-muted) 5%, transparent); }
      .box .box { background: color-mix(in srgb, var(--text-muted) 6%, transparent); }
      .box > .in { position: absolute; inset: 0; pointer-events: none; }
      .box > .in > * { pointer-events: auto; }
      /* Room on the right for the mark of an inner view: the box is as wide as its label. */
      .box > .hd { position: absolute; left: 11px; top: 6px; display: flex; flex-direction: column; align-items: flex-start; gap: 1px;
        white-space: nowrap; justify-content: flex-start; padding-right: 22px; }
      .box > .hd .line { display: flex; align-items: center; gap: 8px; }
      .box > .hd .name { display: inline-flex; align-items: center; gap: 5px; }
      .box > .hd { cursor: pointer; }
      .box.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; }
      .box > .hd .spread { font-size: 11px; color: var(--text-2); font-variant-numeric: tabular-nums; }

      .node { z-index: 1; width: max-content; min-width: 120px; box-sizing: border-box;
        display: flex; flex-direction: column; gap: 7px; padding: 8px 10px 9px;
        border-radius: 10px; border: 1px solid var(--line); background: var(--card); transition: border-color 0.3s, box-shadow 0.3s;
        cursor: pointer; box-shadow: var(--ex, 0 0 0 0 transparent); }
      /* An agent task's node: a thin accent along its left side, the colour the timeline gives agent tasks; a Python task's stays neutral. */
      .node.agent { --ex: inset 3px 0 0 -1px color-mix(in srgb, var(--agent) 60%, transparent); }
      .node .k-ic { width: 16px; height: 16px; margin-right: 6px; border-radius: 4px; font-size: 9.5px; }
      .node .nm { display: flex; align-items: center; min-width: 0; gap: 0; }
      .node .right { display: flex; align-items: center; gap: 8px; }
      /* The mark of an inner view: at the top right of a function node and of a loop box alike. */
      .cue { display: block; line-height: 0; }
      .box > .cue { position: absolute; top: 9px; right: 10px; }
      .node.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; }
      .node.flow { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--line2); }
      .node.cur { border-color: var(--status-running); }
      .node.flow.cur { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--status-running), 0 0 14px var(--status-running-bg); }
      .node:not(.flow).cur { box-shadow: var(--ex, 0 0 0 0 transparent), 0 0 14px var(--status-running-bg); }
      .node.fail { border-color: color-mix(in srgb, var(--status-failed) 55%, transparent); }
      .node:focus-within { border-color: var(--text-2); }
      .hd { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
      .name { all: unset; cursor: pointer; font-family: var(--mono); font-weight: 600; font-size: 12.5px; color: var(--text);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; }
      .name:hover { text-decoration: underline; }
      .name:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
      .count { font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
      .ex { display: flex; flex-wrap: wrap; gap: 0 10px; font-size: 11px; line-height: 1.5;
        max-width: max(98px, calc(var(--cols) * var(--m) + (var(--cols) - 1) * var(--g))); }
      .ex .err { color: var(--status-failed); }
      .ex .warn { color: var(--status-attention); }
      .ex .live { color: var(--status-running); }
      .ex .mut { color: var(--text-muted); }

      .marks { display: grid; grid-template-columns: repeat(var(--cols), var(--m)); gap: var(--g); }
      .slot { width: var(--m); height: var(--m); }
      .mark { width: var(--m); height: var(--m); padding: 0; margin: 0; border: 0; border-radius: 50%; background: var(--status-done); opacity: 0.9;
        cursor: pointer; position: relative; transition: opacity 0.2s, transform 0.15s, background 0.3s; }
      .mark.skipped { background: var(--status-muted); opacity: 0.55; }
      .mark.running { background: var(--status-running); opacity: 1; animation: breathe 1.4s ease-in-out infinite; }
      .mark.pending { background: transparent; box-shadow: inset 0 0 0 1.5px var(--line2); }
      .mark.blocked { border-radius: 2px; background: repeating-linear-gradient(135deg, transparent 0 2px, color-mix(in srgb, var(--status-attention) 55%, transparent) 2px 3px);
        box-shadow: inset 0 0 0 1.5px var(--status-attention); opacity: 1; }
      .mark.failed { border-radius: 2px; background: var(--status-failed); opacity: 1; }
      .big .mark.failed::after { content: '✕'; position: absolute; inset: 0; display: grid; place-items: center; color: var(--bg);
        font-size: calc(var(--m) - 3px); line-height: 1; font-weight: 700; }
      /* A unit that ran more than 1 pass: its number in the mark; a small mark has a hole instead. */
      .mark[data-n]::after { content: ''; position: absolute; inset: 32%; border-radius: 50%; background: var(--card); }
      .big .mark[data-n]::after { content: attr(data-n); inset: 0; display: grid; place-items: center; border-radius: 0; background: none;
        font: 700 max(7px, calc(var(--m) - 4px)) / 1 var(--sans); color: var(--bg); letter-spacing: -0.5px; }
      .big .mark.failed[data-n]::after, .big .mark.running[data-n]::after { color: var(--bg); }
      .big .mark.pending[data-n]::after, .big .mark.blocked[data-n]::after, .big .mark.skipped[data-n]::after { color: var(--text); }
      .mark:hover, .mark:focus-visible { transform: scale(1.4); outline: var(--focus-width) solid var(--text); outline-offset: 1px; z-index: 2; }
      .mark.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; z-index: 2; }
      .taskchip.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 1px; }
      .hl .mark:not(.on) { opacity: 0.16; }
      .hl .mark.on { transform: scale(1.2); }
      .mx.hl .mark:not(.on) { opacity: 0.4; }
      @media (prefers-reduced-motion: reduce) {
        .mark, .node { transition: none; }
        .mark.running { animation: none; background: linear-gradient(90deg, var(--status-running) 50%, transparent 50%); box-shadow: inset 0 0 0 1.5px var(--status-running); }
      }

      .sbar { display: flex; width: 220px; height: 10px; border-radius: 3px; overflow: hidden; background: var(--track); gap: 1px; }
      .sbar i { display: block; min-width: 2px; height: 100%; }
      .sbar .done { background: var(--status-done); opacity: 0.85; }
      .sbar .running { background: var(--status-running); }
      .sbar .pending { background: var(--line2); }
      .sbar .failed { background: var(--status-failed); }
      .sbar .blocked { background: repeating-linear-gradient(135deg, var(--status-attention-bg) 0 2px, color-mix(in srgb, var(--status-attention) 60%, transparent) 2px 3px); }
      .sbar .skipped { background: var(--status-muted); opacity: 0.5; }
      .fails { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; max-width: 220px; font-size: 11px; color: var(--text-muted); }
      .fails .taskchip { color: var(--status-failed); border-color: color-mix(in srgb, var(--status-failed) 45%, transparent); }
      .fails .taskchip:focus-visible { outline: var(--focus-width) solid var(--text); outline-offset: 1px; }
      .hl .fails .taskchip:not(.on) { opacity: 0.4; }

      /* A loop's passes: centred in the frame, the line above as wide as the table (it adds no width of its own). */
      .mxframe { display: grid; grid-template-columns: minmax(0, 1fr); place-items: center; padding: 14px 16px; }
      /* At least wide enough for the loop's name and the sort beside it: a narrower table is stretched to it. */
      .mxblock { display: flex; flex-direction: column; width: fit-content; max-width: 100%; min-width: min(100%, 27rem); }
      .mxbar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; margin-bottom: 8px; font-size: 12px; color: var(--text-2);
        width: 0; min-width: 100%; box-sizing: border-box; }
      .mxbar .cap { color: var(--text); font-weight: 600; }
      .mxbar .sum { flex: 1 0 100%; min-width: 0; }
      .mxbar .f { white-space: nowrap; }
      .sep { color: var(--text-muted); }
      .mxbar label { display: inline-flex; align-items: center; gap: 6px; margin-left: auto; color: var(--text-muted); font-size: 11.5px; white-space: nowrap; }
      .mxbar select { font: inherit; font-size: 11.5px; color: var(--text); background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 2px 6px; }
      .mxbar select:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
      .mx { overflow: auto; max-width: 100%; max-height: max(${lc}px, ${cc*100}vh); border-radius: 6px; border: 1px solid var(--line); }
      table.matrix { border-collapse: separate; border-spacing: 0; font-size: 11px; width: 100%; min-width: max-content; }
      .matrix th, .matrix td { padding: 0 6px; height: ${fc}px; border-bottom: 1px solid var(--line); white-space: nowrap; }
      .matrix thead th { position: sticky; z-index: 2; background: var(--panel2); color: var(--text-muted); font-weight: 500; text-align: center; height: 22px; }
      .matrix thead th.nh { font-family: var(--mono); color: var(--text-2); font-weight: 600; max-width: 110px; overflow: hidden; text-overflow: ellipsis; }
      .matrix thead th.pass { color: var(--text-2); }
      .matrix thead th.loop { font-family: var(--mono); }
      .matrix .uh, .matrix tbody th { position: sticky; left: 0; z-index: 1; background: var(--panel); text-align: left; }
      .matrix thead .uh { z-index: 3; }
      .matrix thead .uh, .matrix thead .pn { background: var(--panel2); }
      .matrix tbody th { font-family: var(--mono); font-weight: 600; color: var(--text); max-width: 220px; overflow: hidden; text-overflow: ellipsis; }
      .matrix tbody th.none { font-family: var(--sans); font-weight: 500; color: var(--text-muted); }
      .matrix .pn { text-align: right; color: var(--text-muted); font-variant-numeric: tabular-nums; }
      .matrix .pn.many { color: var(--text); font-weight: 600; }
      .matrix td.c { text-align: center; --m: 12px; }
      .matrix td.c .mark { vertical-align: middle; }
      .matrix .g0 { border-left: 1px solid var(--line2); }
      .matrix .g1 { border-left: 1px dashed var(--line); }
      .matrix tbody tr:hover td, .matrix tbody tr:hover th { background-color: color-mix(in srgb, var(--text-muted) 8%, transparent); }
      .matrix tbody tr.on td, .matrix tbody tr.on th { background-color: var(--accent-bg); }
      .matrix .gap td { padding: 0; border: 0; }

      .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-bottom: 8px; font-size: 12px; }
      .crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; list-style: none; margin: 0; padding: 0; }
      .crumbs li { display: inline-flex; align-items: center; gap: 4px; }
      .crumbs .sep { color: var(--text-muted); }
      .crumbs button { all: unset; cursor: pointer; color: var(--accent); font-family: var(--mono); }
      .crumbs button:hover { text-decoration: underline; }
      .crumbs button:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
      .crumbs [aria-current] { font-family: var(--mono); color: var(--text); font-weight: 600; }
      .pin { display: inline-flex; align-items: center; gap: 8px; color: var(--text-2); }
      .pin b { font-family: var(--mono); }

      /* The legend on the left, the tools at the right end of the first line, in every view. */
      .foot { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 6px 14px; margin-top: 6px; }
      .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11px; color: var(--text-muted); }
      .legend > span { white-space: nowrap; }
      .legend span { display: inline-flex; align-items: center; gap: 6px; }
      .legend .mark { --m: 12px; cursor: default; animation: none; }
      .legend .mark:hover { transform: none; outline: none; }
      .legend svg path { stroke: var(--line2); stroke-width: 1.5; fill: none; }
      .legend .k-ic { width: 14px; height: 14px; margin: 0; border-radius: 4px; font-size: 8.5px; }
      .list .k-ic { width: 16px; height: 16px; border-radius: 4px; font-size: 9.5px; }
      .matrix thead th.nh .k-ic { width: 14px; height: 14px; margin-right: 5px; border-radius: 4px; font-size: 8.5px; vertical-align: -2px; }

      .main { position: relative; min-width: 0; }
      .missing { margin-bottom: 8px; font-size: 12px; color: var(--status-attention); }
      .missing code { font-family: var(--mono); }

      /* the selection's card: beside the item, joined to it by a pointer, in the accent of the item's outline */
      .insp { position: absolute; left: 0; top: 0; z-index: 6; width: 272px; max-width: calc(100% - 16px); box-sizing: border-box;
        display: flex; flex-direction: column; gap: 9px; padding: 10px 12px 12px; border-radius: 10px;
        border: 1px solid var(--accent); background: var(--card); font-size: 12px; overflow: visible;
        box-shadow: 0 12px 32px color-mix(in srgb, var(--shadow) 55%, transparent); visibility: hidden;
        animation: insp-in 0.12s var(--ease) both; }
      .insp.placed { visibility: visible; }
      .insp .scroll { display: flex; flex-direction: column; gap: 9px; min-height: 0; overflow: auto; }
      .insp .ptr { position: absolute; width: 10px; height: 10px; background: var(--card); border: 1px solid var(--accent);
        transform: rotate(45deg); }
      .insp[data-side='right'] .ptr { left: -6px; top: calc(var(--arrow) - 5px); border-top: 0; border-right: 0; }
      .insp[data-side='left'] .ptr { right: -6px; top: calc(var(--arrow) - 5px); border-bottom: 0; border-left: 0; }
      .insp[data-side='below'] .ptr { top: -6px; left: calc(var(--arrow) - 5px); border-bottom: 0; border-right: 0; }
      .insp[data-side='above'] .ptr { bottom: -6px; left: calc(var(--arrow) - 5px); border-top: 0; border-left: 0; }
      /* a narrow screen: a sheet under the frame, naming the item */
      .insp.sheet { position: sticky; bottom: 8px; width: auto; max-width: none; margin-top: 8px; visibility: visible; }
      .insp.sheet .ptr { display: none; }
      @keyframes insp-in { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: none; } }
      .insp h4 { margin: 0; display: flex; align-items: center; gap: 7px; font-family: var(--mono); font-size: 13px; font-weight: 600;
        color: var(--text); overflow-wrap: anywhere; }
      .insp h4 .mark { --m: 11px; flex: none; cursor: default; animation: none; }
      .insp h4 .mark:hover { transform: none; outline: none; }
      .insp h4 .k-ic { width: 18px; height: 18px; margin: 0; border-radius: 5px; font-size: 10px; }
      .insp .sub { color: var(--text-2); }
      .insp dl { display: grid; grid-template-columns: fit-content(42%) minmax(0, 1fr); gap: 4px 12px; margin: 0; }
      .insp dt { color: var(--text-muted); word-break: keep-all; overflow-wrap: break-word; }
      .insp dd { margin: 0; color: var(--text); overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
      .insp dd .err { color: var(--status-failed); }
      .insp dd .warn { color: var(--status-attention); }
      .insp .acts { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding-top: 2px; }
      .insp .go { all: unset; cursor: pointer; color: var(--accent); overflow-wrap: anywhere; }
      .insp .go.primary { font-weight: 600; }
      .insp .go:hover { text-decoration: underline; }
      .insp .go:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
      .insp .acts .switch { margin-left: auto; }
      .keys { grid-column: 1 / -1; font-size: 11px; color: var(--text-muted); display: none; }
      .keys span { white-space: nowrap; }
      :host(:focus-within) .keys { display: block; }
      .switch { all: unset; cursor: pointer; font-size: 11.5px; color: var(--text-2); padding: 2px 8px; border-radius: 6px; border: 1px solid var(--line); }
      .switch:hover { color: var(--text); border-color: var(--line2); }
      .switch:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }

      /* The table: across the frame's content box, the name and status as wide as their content, the relations sharing the rest. */
      /* A shadow at an edge the table scrolls past: a lid over it at the end, a shadow fixed to the frame. */
      .tframe { overflow: auto; padding: 0 12px 10px;
        background:
          linear-gradient(transparent, var(--well) 70%) center bottom / 100% 28px no-repeat local,
          radial-gradient(farthest-side at 50% 100%, color-mix(in srgb, var(--text-muted) 30%, transparent), transparent) center bottom / 100% 12px no-repeat scroll,
          var(--well); }
      /* on a narrow screen it keeps room for its relations and scrolls across */
      table.list { width: 100%; min-width: 64rem; border-collapse: separate; border-spacing: 0; font-size: 12px; font-variant-numeric: tabular-nums; }
      .list th, .list td { text-align: left; vertical-align: middle; padding: 6px 10px; border-bottom: 1px solid var(--line); }
      .list .fit { width: 1%; white-space: nowrap; }
      /* a header is as wide as its words, and stays at the top of the frame */
      .list thead th { position: sticky; top: 0; z-index: 2; background: var(--well); color: var(--text-muted); font-weight: 500; font-size: 11px;
        white-space: nowrap; padding-top: 10px; }
      .list tbody th { font-weight: 600; }
      .list td { color: var(--text-2); }
      .list tbody tr { cursor: pointer; }
      .list tbody tr:hover > * { background-color: color-mix(in srgb, var(--text-muted) 8%, transparent); }
      .list tbody tr.sel > * { background-color: var(--accent-bg); }
      .list tbody tr.sel > th { box-shadow: inset 2px 0 0 var(--accent); }
      .list .nm { display: inline-flex; align-items: center; gap: 8px; vertical-align: middle; }
      .list .nm .k-ic { margin: 0 -2px 0 0; }
      .list .nm .in-ic { margin-right: -2px; }
      .list .name { max-width: 32ch; }
      .loopchip { display: inline-flex; align-items: center; gap: 4px; font-family: var(--sans); font-weight: 400; }
      .loopchip .ic { color: var(--text-muted); }
      .loopchip:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
      .list .st .n { color: var(--text); }
      .list .st .err { color: var(--status-failed); }
      .list .st .warn { color: var(--status-attention); }
      .list .st .live { color: var(--status-running); }
      .list .st .mut { color: var(--text-muted); }
    `]}willUpdate(e){if(e.has(`run`)&&this.orders.clear(),e.has(`layer`)&&e.get(`layer`)!==void 0){this.moved=!1,this.active.clear(),this.cell=null,this.scrollRow=0;let e=this.renderRoot instanceof ShadowRoot?this.renderRoot.activeElement:null;this.refocus=e!==null&&!e.closest(`.views`),this.replacing?this.replacing=!1:this.missing=``}if(e.has(`run`)&&e.get(`run`)!==void 0&&(this.missing=``),!e.has(`plan`)&&!e.has(`layer`)&&!e.has(`run`)&&!e.has(`down`))return;if(this.auto=Is(this.plan),this.segments=this.layer?this.layer.split(`/`):this.auto,this.layer&&this.plan.nodes.length){let e=Rs(this.plan,this.segments);e?e.join(`/`)!==this.layer&&(this.segments=e,this.setLayer(e.join(`/`)===this.auto.join(`/`)?``:e.join(`/`))):(this.missing=this.layer,this.segments=this.auto,this.setLayer(``))}let{path:t,loop:n}=Ls(this.segments),r=t.join(`/`);if(this.graph=Fs(this.plan,t,this.orders.get(r),this.down),this.orders.set(r,this.graph.order),this.matrix=n?Ks(this.plan,t,n,this.graph.order):null,e.has(`plan`)){this.byKey=new Map(this.plan.nodes.map(e=>[e.key,e])),this.waiters=new Map;for(let e of this.plan.nodes)for(let t of e.after??[])(this.waiters.get(t)??this.waiters.set(t,[]).get(t))?.push(e.key)}}disconnectedCallback(){super.disconnectedCallback(),this.removeEventListener(`wheel`,this.onWheel),this.removeEventListener(`click`,this.onClickCapture,{capture:!0}),this.removeEventListener(`keydown`,this.onEscape),this.removeEventListener(`keydown`,this.onTabToCard),this.resize?.disconnect(),this.resize=void 0}connectedCallback(){super.connectedCallback(),this.addEventListener(`wheel`,this.onWheel,{passive:!1}),this.addEventListener(`click`,this.onClickCapture,{capture:!0}),this.addEventListener(`keydown`,this.onEscape),this.addEventListener(`keydown`,this.onTabToCard)}updated(e){this.resize||(this.resize=new ResizeObserver(()=>{this.fit(),this.anchorCard()}),this.resize.observe(this)),this.place(),(this.refocus||this.cameFrom)&&this.restoreFocus(),this.anchorCard(),e.has(`sel`)&&this.selectionChanged()}anchor(){let e=this.renderRoot.querySelector(`.main > .frame`),t=e?.querySelector(`tr.sel > th`);if(e&&t)return{item:t,clear:t,frame:e};let n=e?.querySelector(`.mark.sel, .taskchip.sel, .node.sel, .box.sel`);if(!e||!n)return null;let r=n.classList.contains(`box`)?n.querySelector(`:scope > .hd`)??n:n;return{item:r,clear:r.closest(`.node`)??n,frame:e}}anchorCard(){let e=this.renderRoot.querySelector(`.insp`),t=e&&!this.down?e.querySelector(`.scroll`).scrollHeight+24+16:0;if(t!==this.cardRoom&&(t>this.frameH||this.cardRoom>0)&&(this.cardRoom=t,this.matrix?this.requestUpdate():this.fit()),!e||this.down)return;let n=this.anchor(),r=this.renderRoot.querySelector(`.main`);if(!n||!r){e.classList.remove(`placed`);return}let i=r.getBoundingClientRect(),a=e=>({left:e.left-i.left,top:e.top-i.top,width:e.width,height:e.height}),o=a(n.item.getBoundingClientRect()),s=a(n.clear.getBoundingClientRect()),c=a(n.frame.getBoundingClientRect()),l=n.frame.querySelector(`.mx`),u=tc(o,l?a(l.getBoundingClientRect()):c,{width:0,height:0}).shown,d=e.querySelector(`.scroll`);d&&(d.style.maxHeight=`${Math.max(120,c.height-16-24)}px`);let f={width:e.offsetWidth,height:e.offsetHeight},p=tc(s,c,f,o);!p.fits&&n.clear!==n.item&&!n.clear.classList.contains(`node`)&&(p=tc(o,c,f)),e.classList.toggle(`placed`,p.shown&&u),e.dataset.side=p.side,e.style.left=`${p.x}px`,e.style.top=`${p.y}px`,e.style.setProperty(`--arrow`,`${p.arrow}px`)}anchorFocus(){let e=this.anchor();return e?e.item.matches(`button`)?e.item:e.item.querySelector(`.name`):null}selectionChanged(){for(let e of this.renderRoot.querySelectorAll(`[aria-describedby="insp"]`))e.removeAttribute(`aria-describedby`);this.anchorFocus()?.setAttribute(`aria-describedby`,`insp`);let e=this.renderRoot.querySelector(`.insp`),t=e?.querySelector(`h4`)?.textContent?.trim()??``,n=e?.querySelector(`[data-status]`)?.textContent?.trim()??``,r=t?H(t,n):``;r!==this.announced&&(this.announced=r),this.down&&this.whenReleased(()=>this.revealOverSheet())}whenReleased(e){if(!this.pressed)return e();globalThis.addEventListener(`pointerup`,()=>setTimeout(e),{once:!0})}revealOverSheet(){let e=this.anchor()?.item;if(!e)return;let t=e.getBoundingClientRect(),n=this.renderRoot.querySelector(`.insp`)?.getBoundingClientRect(),r=Math.min(globalThis.innerHeight,n?.top??1/0);(t.top<0||t.bottom>r)&&e.scrollIntoView({block:`center`})}onCardKey(e){let t=[...e.currentTarget.querySelectorAll(`button`)],n=this.renderRoot instanceof ShadowRoot?this.renderRoot.activeElement:null;if(e.key===`Tab`&&e.shiftKey&&n===t[0]){let t=this.anchorFocus();if(!t)return;e.preventDefault(),this.quiet=!0,t.focus(),this.quiet=!1}else e.key===`Escape`&&(this.quiet=!0,this.anchorFocus()?.focus(),this.quiet=!1)}place(){let e=this.renderRoot.querySelector(`.dag`);if(!e)return;let t=new Map;for(let n of e.querySelectorAll(`[data-id]`))t.set(n.dataset.id??``,{w:n.offsetWidth,h:n.offsetHeight});let n=this.graph,r=JSON.stringify([n.path,n.slots,n.routes.map(e=>e.steps.map(e=>e.id)),this.down,[...t]]);if(r===this.layKey)return this.fit();this.layKey=r,this.layPath=n.path.join(`/`),this.lay=Hs(n,t,this.down),this.updateComplete.then(()=>this.fit())}restoreFocus(){let e=this.cameFrom;this.refocus=!1,this.cameFrom=``;let t=this.renderRoot,n=null;if(e.startsWith(`loop:`))n=t.querySelector(`.box[data-box="${CSS.escape(e)}"] > .hd .name`);else if(e){let r=this.graph.nodes.find(t=>t.type===`flow`&&t.name===e);r&&(n=t.querySelector(`.node[data-id="${CSS.escape(r.id)}"] [tabindex="0"]`))}this.quiet=!0,(n??t.querySelector(`.mark[tabindex="0"], .node .name, .crumbs button`))?.focus(),this.quiet=!1}focusSelect(e){this.quiet||this.select(e)}setLayer(e){this.replacing=!0,A(this,`ca-navigate`,{layer:e,unit:this.unit,sel:this.sel,replace:!0})}go(e,t=this.unit){let n=this.auto.join(`/`),r=e.join(`/`);A(this,`ca-navigate`,{layer:r===n?``:r,unit:t})}chosen(){return rc(this.graph,this.matrix,this.sel)}select(e){e!==this.sel&&A(this,`ca-navigate`,{sel:e})}primary(e){if(e.type===`mark`)return this.open(e.mark);if(e.type===`box`)return this.go([...this.segments,e.box.id]);if(e.node.type===`flow`)return this.go([...this.graph.path,e.node.name]);this.tasksOf(e.node)}tasksOf(e){A(this,`ca-navigate`,{tab:`tasks`,kind:e.kinds.length===1?e.kinds[0]:``})}onItemClick(e,t){e.target.closest(`.mark, .taskchip, .node, .box`)===e.currentTarget&&(e.stopPropagation(),!(e.detail>=2)&&this.select(t))}onItemDblClick(e,t){if(e.target.closest(`.mark, .taskchip, .node, .box`)!==e.currentTarget)return;e.stopPropagation();let n=rc(this.graph,this.matrix,t);n&&this.primary(n)}onNameKey(e,t){if(e.key!==`Enter`)return;e.preventDefault();let n=rc(this.graph,this.matrix,t);n&&this.primary(n)}crumbs(){let e=this.segments,t=this.unit;if(!e.length&&!t)return O;let{path:n,loop:r}=Ls(e),i=[...n.map((e,t)=>({name:ps(e),tip:e,to:n.slice(0,t+1)})),...(r?r.slice(os.length).split(`.`):[]).map((e,t,r)=>{let i=os+r.slice(0,t+1).join(`.`),a=this.graph.boxes.find(e=>e.id===i)?.file||this.matrix?.box.file||``,o=/^\d+$/.test(e);return{name:M(o?j`Loop at ${this.where(e,a)}`:`Loop`),tip:o&&a?`${a}:${e}`:``,to:[...n,i]}})];return D`<div class="bar">
      ${e.length?D`<nav aria-label=${M(`Pipeline layer`)}>
            <ol class="crumbs">
              <li><button type="button" @click=${()=>this.go([])}>${M(`Pipeline`)}</button></li>
              ${i.map((e,t)=>D`<li><span class="sep" aria-hidden="true">›</span>
                  ${t===i.length-1?D`<span aria-current="page" title=${e.tip||O}>${e.name}</span>`:D`<button type="button" title=${e.tip||O} @click=${()=>this.go(e.to)}>${e.name}</button>`}</li>`)}
            </ol>
          </nav>`:O}
      ${t?D`<span class="pin">${M(j`Unit: ${t}`)}
            <button type="button" class="switch" @click=${()=>A(this,`ca-navigate`,{unit:``})}>${M(`Clear highlight`)}</button></span>`:O}
    </div>`}fit(){let e=this.clientWidth,t=e>0&&e<sc;t!==this.down&&(this.down=t);let n=this.lay;if(!n||this.matrix)return;let r=this.renderRoot.querySelector(`.frame`)?.clientWidth||e,i=ic(n.w,n.h,r,t?1/0:Math.max(lc,cc*window.innerHeight));this.fitK=i.k;let a=t?i.h:Math.max(i.h,this.cardRoom),o=i.y;this.moved?a>this.frameH&&(this.frameH=a):(a!==this.frameH&&(this.frameH=a),(i.k!==this.view.k||i.x!==this.view.x||o!==this.view.y)&&(this.view={k:i.k,x:i.x,y:o}))}zoomTools(){let e=!this.moved&&this.fitK>=1;return D`<button type="button" aria-label=${M(`Zoom out`)} title=${M(`Zoom out (Ctrl + scroll)`)} @click=${()=>this.zoomBy(1/1.25)}>−</button>
      <button type="button" aria-label=${M(`Zoom in`)} title=${M(`Zoom in (Ctrl + scroll)`)} @click=${()=>this.zoomBy(1.25)}>+</button>
      <button type="button" ?disabled=${e} @click=${()=>this.showAll()}>${M(`Show all`)}</button>`}showAll(){this.moved=!1,this.fit(),this.requestUpdate()}zoomBy(e,t=(this.renderRoot.querySelector(`.frame`)?.clientWidth??this.clientWidth)/2,n=this.frameH/2){this.moved=!0,this.view=ac(this.view,e,t,n,Math.min(1,this.fitK)/2,uc)}onPointerDown(e){this.pressed=!0,globalThis.addEventListener(`pointerup`,()=>this.pressed=!1,{once:!0}),!(e.button!==0||e.target.closest(`.tools`)||this.down&&e.pointerType!==`mouse`)&&(this.pan={id:e.pointerId,px:e.clientX,py:e.clientY,x:this.view.x,y:this.view.y,far:!1})}onPointerMove(e){let t=this.pan;if(!t||t.id!==e.pointerId)return;let n=e.clientX-t.px,r=e.clientY-t.py;!t.far&&Math.hypot(n,r)<dc||(t.far||(t.far=!0,e.currentTarget.setPointerCapture(e.pointerId),e.currentTarget.classList.add(`drag`)),this.moved=!0,this.view={...this.view,x:t.x+n,y:t.y+r})}onPointerUp(e){let t=this.pan;t&&t.id===e.pointerId&&(this.pan=null,e.currentTarget.classList.remove(`drag`),t.far&&(this.swallowClick=!0))}reveal(e){let t=this.renderRoot.querySelector(`.frame`);if(!t)return;let n=t.getBoundingClientRect(),r=e.getBoundingClientRect(),i=0,a=0;r.left<n.left+24?i=n.left+24-r.left:r.right>n.right-24&&(i=n.right-24-r.right),r.top<n.top+24?a=n.top+24-r.top:r.bottom>n.bottom-24&&(a=n.bottom-24-r.bottom),(i||a)&&(this.moved=!0,this.view={...this.view,x:this.view.x+i,y:this.view.y+a})}get hl(){let e=this.hover===null?this.chosen():null,t=e?.type===`mark`?e.mark.unit||e.mark.key:null;return this.hover??t??(this.unit||null)}lit(){let e=this.hl;if(e===null)return null;let t=this.plan.nodes.filter(t=>t.unit?t.unit===e:t.key===e).map(e=>e.key),n=new Set(t),r=e=>{let r=new Set(t),i=[...t];for(let t=i.pop();t!==void 0;t=i.pop())for(let a of e(t))r.has(a)||(r.add(a),n.add(a),i.push(a))};return r(e=>this.waiters.get(e)??[]),r(e=>this.byKey.get(e)?.after??[]),n}render(){if(!this.plan.nodes.length)return D`<div class="blank" style="padding:24px">${this.live?M(`No tasks scheduled yet`):M(`No tasks scheduled`)}</div>`;let{outcomes:e}=Zi(this.journal,this.plan),t=t=>{let n=e.get(t);return n?va(n,e,this.run):``},n=this.matrix,r=!!n||this.asTable,i=n?this.matrixView(n,t):this.asTable?this.table():this.dag(t);return D`${this.crumbs()}${this.missingLine()}
      <div class="main">${i}${this.inspector(t)}</div>
      <div class="foot">
        ${this.legend()}
        <div class="tools">${r?O:this.zoomTools()}${this.viewSwitch(r)}</div>
        <div class="keys">${this.keyHints().map((e,t)=>D`${t?` | `:``}<span>${e}</span>`)}</div>
      </div>`}viewSwitch(e){return D`<cae-segmented class="views" .options=${[{value:`graph`,label:M(`Graph`,{id:`view-graph`,desc:`Button: show the pipeline as a graph`})},{value:`table`,label:M(`Table`,{id:`view-table`,desc:`Button: show the pipeline as a table`})}]} .value=${e?`table`:`graph`} label=${M(`View`)}
      @cae-change=${e=>e.detail.value===`table`?this.showTable():this.showGraph()}></cae-segmented>`}showGraph(){if(this.asTable=!1,!this.matrix)return;let e=this.segments[this.segments.length-1]??``,t=zs(this.segments,this.auto)??[],n=this.auto.join(`/`);A(this,`ca-navigate`,{layer:t.join(`/`)===n?``:t.join(`/`),unit:this.unit,sel:e})}showTable(){this.matrix||(this.asTable=!0)}missingLine(){if(!this.missing)return O;let e=this.missing.split(`/`),t=e[e.length-1]||this.missing;return D`<div class="missing" role="status" title=${this.missing}>${M(D`No layer <code>${t}</code> in this run`)}</div>`}keyHints(){let e=this.sel?M(`Esc: clear selection`):zs(this.segments,this.auto)?M(`Esc: up a level`):``;return(this.matrix?[M(`Arrow keys: marks`),M(`Enter: open`),e]:this.asTable?[M(`Tab: next row`),M(`Enter: open`),e]:[M(`Tab: next node`),M(`Arrow keys: marks`),M(`Shift + arrow keys: earlier and later tasks`),M(`Enter: open`),e]).filter(Boolean)}dag(e){let t=this.graphView(e),n=this.view;return D`<div class="frame gframe ${this.down?`down`:``}" style="height:${Math.round(this.frameH)}px"
        @pointerdown=${e=>this.onPointerDown(e)} @pointermove=${e=>this.onPointerMove(e)}
        @pointerup=${e=>this.onPointerUp(e)} @pointercancel=${e=>this.onPointerUp(e)}
        @click=${e=>!e.target.closest(`.node, .box, .stub, .tools`)&&this.select(``)}>
        <div class="stage view" style="transform:translate(${n.x}px,${n.y}px) scale(${n.k})">${t}</div>
      </div>`}at(e,t){let n=this.lay?.at[e];if(!n)return`left:0;top:0`;let r=t?t.x+1:0,i=t?t.y+1:0;return`left:${n.x-r}px;top:${n.y-i}px`}graphView(e){let t=this.lit(),n=this.graph,r=this.lay,i=new Map(n.nodes.map(e=>[e.id,e])),a=new Map(n.boxes.map(e=>[e.id,e])),o=new Map(n.stubs.map(e=>[e.id,e])),s=e=>(n.slots[e]??[]).flat().filter(e=>!Z(e)),c=(n,r)=>{let s=a.get(n);if(s)return this.box(s,r,(e,t)=>c(e,t));let l=o.get(n);if(l)return D`<span class="stub" data-id=${l.id} style=${this.at(l.id,r)} title=${M(`Outside this layer`)}>${l.label}</span>`;let u=i.get(n);return u?this.node(u,r,e,t):O},l=!!r&&n.nodes.every(e=>r.at[e.id]),u=r?.w??0,d=r?.h??0;return D`<div class="dag ${this.down?`down`:``} ${t?`hl`:``} ${l?``:`unplaced`}" style="width:${u}px;height:${d}px"
      @mouseleave=${()=>this.hover=null}>
      <svg class="edges" aria-hidden="true" width=${u} height=${d}>
        <defs>
          <marker id="arr" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
            <path d="M0,0.5 L8,4 L0,7.5 z" fill="var(--line2)" stroke="none"></path>
          </marker>
          <marker id="arr-ret" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
            <path class="ret-tip" d="M0,0.5 L8,4 L0,7.5 z"></path>
          </marker>
        </defs>
        ${(r?.edges??[]).map(e=>Re`<path class=${e.type} d=${Zs(e.runs,r?.down)} marker-end="url(#arr)"></path>`)}
        ${(r?.returns??[]).map(e=>Re`<path class="ret" data-box=${e.box} d=${Xs(e,r?.down)} marker-end="url(#arr-ret)"></path>`)}
      </svg>
      ${B(s(``),e=>e,e=>c(e,null))}
    </div>`}box(e,t,n){let r=this.lay?.at[e.id]??null,i=M(j`Loop at ${this.where(e.loop,e.file)}`),a=e.spread.length>1?po(e.spread):``,o=(this.graph.slots[e.id]??[]).flat().filter(e=>!Z(e)),s=r?`;width:${r.w}px;height:${r.h}px`:``;return D`<section class="box ${this.sel===e.id?`sel`:``}" role="group" data-box=${e.id} style=${this.at(e.id,t)+s}
        aria-label=${H(i,uo(e.passes),a)}
        @click=${t=>this.onItemClick(t,e.id)} @dblclick=${t=>this.onItemDblClick(t,e.id)}>
      <div class="hd" data-id=${`lbl:${e.id}`}>
        <span class="line">
          <button type="button" class="name" title=${H(mo(),i)} aria-pressed=${this.sel===e.id}
            @focus=${()=>this.focusSelect(e.id)} @keydown=${t=>this.onNameKey(t,e.id)}>${gc()}${mo()}</button>
          <span class="count">${uo(e.passes)}</span>
        </span>
        ${a?D`<span class="spread" title=${M(`Units by number of passes`)}>${a}</span>`:O}
      </div>
      <span class="cue" aria-hidden="true">${_c()}</span>
      <div class="in">${B(o,e=>e,e=>n(e,r))}</div>
    </section>`}node(e,t,n,r){let i=e.counts,a=i.failed||e.errors?`fail`:i.running?`cur`:i.done+i.skipped===i.total?`done`:``,o=Ws(e),s=o?{id:e.id,label:e.label,slots:vc(e).filter(e=>e?.state===`failed`),grid:{cols:hc,size:12,gap:4}}:{id:e.id,label:e.label,slots:vc(e),grid:yc(e,this.graph.units.length)},c=this.exceptions(e),l=this.sel===e.id,u=e.type===`flow`?H(M(j`Function ${e.name}`),this.doneOf(i)):H(e.label,this.executorWord(e),this.doneOf(i)),d=e.executor===`mixed`?D`${X(!1)}${X(!0)}`:e.executor?X(e.executor===`python`):O;return D`<section class="node ${e.type} ${e.executor===`agent`?`agent`:``} ${a} ${l?`sel`:``}" role="group" data-id=${e.id}
      aria-label=${this.nodeLabel(e)}
      style="${this.at(e.id,t)};--cols:${s.grid.cols};--m:${s.grid.size}px;--g:${s.grid.gap}px"
      @click=${t=>this.onItemClick(t,e.id)} @dblclick=${t=>this.onItemDblClick(t,e.id)}>
      <div class="hd">
        <span class="nm">${d}<button type="button" class="name" title=${u} aria-pressed=${l}
          @focus=${()=>this.focusSelect(e.id)} @keydown=${t=>this.onNameKey(t,e.id)}>${e.label}</button></span>
        <span class="right"><span class="count" aria-hidden="true" title=${this.doneOf(i)}>${i.done}/${i.total}</span>${e.type===`flow`?D`<span class="cue" aria-hidden="true">${_c()}</span>`:O}</span>
      </div>
      ${o?this.statusBar(e,s,n,r):this.marks(s,n,r)}
      ${c.length?D`<div class="ex" aria-hidden="true">${c.map(([e,t])=>D`<span class=${e}>${t}</span>`)}</div>`:O}
    </section>`}executorWord(e){return e.executor===`agent`?M(`Agent task`):e.executor===`python`?M(`Python task`):e.executor===`mixed`?H(M(`Agent task`),M(`Python task`)):``}statusBar(e,t,n,r){let i=Gs(e.counts,oc),a=t.slots.slice(0,hc),o=t.slots.length-a.length,s=Math.min(this.active.get(t.id)??0,Math.max(0,a.length-1));return D`<div class="sbar" role="img" aria-label=${this.stateCounts(e.counts)}>
        ${i.map(e=>D`<i class=${e.state} style="width:${e.pct}%" title=${this.countOf(e.state,e.n)}></i>`)}
      </div>
      ${a.length?D`<div class="fails" @keydown=${e=>this.onKey(e,{...t,slots:a,grid:{...t.grid,cols:a.length}})}>
            ${a.map((e,i)=>e?this.mark(t,e,i,i===s,n,r,!0):O)}
            ${o>0?D`<span>${M(j`+${o}`)}</span>`:O}
          </div>`:O}`}marks(e,t,n){let r=Math.min(this.active.get(e.id)??bc(e.slots),e.slots.length-1);return D`<div class="marks ${e.grid.size>=10?`big`:``}" @keydown=${t=>this.onKey(t,e)}>
      ${e.slots.map((i,a)=>i?this.mark(e,i,a,a===r,t,n):D`<span class="slot"></span>`)}
    </div>`}markText(e,t,n,r=``){let i=t.flow?void 0:this.byKey.get(t.key),a=U({kind:e,unit:t.unit}),o=!t.flow&&t.state===`blocked`?n(t.key):``,s=o?M(j`Not started: ${o}`):this.stateWord(t.state),c=i?.attempts??1,l=c>1?M(j`${c} attempts`):``,u=t.passes?fo(t.passes):``,d=t.flow||t.count>1?M(j`${t.count} tasks`):``,f=t.counts?this.notDone(t.counts):[],p=t.error===void 0?[]:[M(`Flow call stopped with an error`),t.error],m=!t.flow&&(t.state===`done`||t.state===`failed`)&&i?.wall_s?P(i.wall_s):``;return{name:a,parts:[s,r,u,l,d,...f,...p,m].filter(Boolean),id:t.flow?M(j`Flow call ${t.key}`):t.key}}open(e){if(e.flow)return this.go([...this.graph.path,e.flow],e.unit||this.unit);let t=this.byKey.get(e.key);A(this,`ca-open-task`,e.state===`blocked`?{key:e.key,view:`input`}:t?.executor===`python`?{key:e.key,view:`output`}:{key:e.key})}mark(e,t,n,r,i,a,o=!1){let{name:s,parts:c}=this.markText(e.label,t,i),l=t.unit||t.key,u=a!==null&&(t.unit!==``&&t.unit===this.hl||t.keys.some(e=>a.has(e))),d=nc(e.id,t),f=this.sel===d?`sel`:``,p=t=>{this.hover=l,this.active.set(e.id,n),this.reveal(t.currentTarget),this.focusSelect(d)},m=[s,c[0]??``].filter(Boolean).join(`
`);return o?D`<button type="button" class="taskchip ${u?`on`:``} ${f}" data-i=${n} tabindex=${r?0:-1}
        title=${m} aria-label=${H(s,...c)} aria-pressed=${!!f}
        @mouseenter=${()=>this.hover=l} @focus=${p} @blur=${()=>this.hover=null}
        @click=${()=>this.select(d)} @dblclick=${()=>this.open(t)}>${t.unit||t.key}</button>`:D`<button type="button" class="mark ${t.state} ${u?`on`:``} ${f}" data-i=${n} data-n=${t.passes??O} tabindex=${r?0:-1}
      title=${m}
      aria-label=${H(s,...c)} aria-pressed=${!!f}
      @mouseenter=${()=>this.hover=l}
      @focus=${p}
      @blur=${()=>this.hover=null}
      @click=${()=>this.select(d)}
      @dblclick=${()=>this.open(t)}></button>`}matrixView(e,t){let n=qs(e.rows,this.sort),r=e.columns,i=this.hl,a=r.map((e,t)=>{let n=r[t-1]?.passes;if(!n)return-1;let i=e.passes.findIndex((e,t)=>e!==n[t]);return i<0?e.passes.length===n.length?-1:Math.min(e.passes.length,n.length):i}),o=e=>a[e]===0?`g0`:(a[e]??-1)>0?`g1`:``,s=e.head.length,c=n.length>pc,l=c?Math.max(0,this.scrollRow-mc):0,u=c?Math.min(n.length,this.scrollRow+60+20):n.length,d=this.cell&&this.cell[0]<n.length?this.cell:this.firstCell(n),f=e.rows.filter(e=>e.unit).length,p=e=>e===0||a[e]===0?`g0`:(a[e]??-1)>0?`g1`:``,m=(t,n,r)=>{let i=`top:${r*22}px`;return t.type===`pass`?D`<th scope="colgroup" colspan=${t.span} class="pass ${p(n)}" style=${i}
          title=${t.box.id===e.box.id?M(j`Loop at ${this.where(t.box.loop,t.box.file)}`):M(j`Nested loop at ${this.where(t.box.loop,t.box.file)}`)}>${lo(t.pass)}</th>`:t.type===`loop`?D`<th scope="colgroup" colspan=${t.span} class="loop ${p(n)}" style=${i}
          title=${M(j`Nested loop at ${this.where(t.box.loop,t.box.file)}`)}>${mo()}</th>`:D`<th scope="col" rowspan=${t.rows} class="nh ${p(n)}" style=${i}
        title=${t.node.type===`flow`?M(j`Function ${t.node.name}`):H(t.node.label,this.executorWord(t.node))}
        aria-label=${t.node.type===`flow`?t.node.label:H(t.node.label,this.executorWord(t.node))}>${t.node.executor&&t.node.executor!==`mixed`?X(t.node.executor===`python`):O}${t.node.label}</th>`},h=t=>{let n=[],r=0;for(let i of e.head[t]??[]){for(;xc(e.head,t,r);)r++;n.push(r),r+=i.span}return n},g=[uo(e.box.passes),e.box.spread.length>1?po(e.box.spread):``,M(f===1?`1 unit`:j`${f} units`)].filter(Boolean),_=this.down?0:Math.round(Math.max(this.frameH,this.cardRoom));return D`<div class="frame mxframe" style=${_?`min-height:${_}px`:``}><div class="mxblock view">
      <div class="mxbar">
        <span class="cap" title=${e.box.file?`${e.box.file}:${e.box.loop}`:O}>${M(j`Loop at ${this.where(e.box.loop,e.box.file)}`)}</span>
        <label>${M(`Sort units`)}
          <select @change=${e=>this.sort=e.target.value}>
            <option value="order" ?selected=${this.sort===`order`}>${M(`Scheduled order`)}</option>
            <option value="passes" ?selected=${this.sort===`passes`}>${M(`Number of passes`)}</option>
            <option value="state" ?selected=${this.sort===`state`}>${M(`Status`,{id:`status`,desc:`The status of a task: done, failed, not started`})}</option>
          </select>
        </label>
        <span class="sum">${g.map((e,t)=>D`${t?D`<span class="sep"> | </span>`:O}<span class="f">${e}</span>`)}</span>
      </div>
      <div class="mx ${i?`hl`:``}" @scroll=${e=>this.onMatrixScroll(e)} @mouseleave=${()=>this.hover=null}>
        <table class="matrix big" role="grid" aria-rowcount=${n.length+s} aria-colcount=${r.length+2}
          aria-label=${H(M(j`Loop at ${this.where(e.box.loop,e.box.file)}`),uo(e.box.passes))}>
          <thead>
            ${e.head.map((e,t)=>{let n=h(t);return D`<tr>
                ${t===0?D`<th scope="col" rowspan=${s} class="uh" style="top:0">${M(`Unit`)}</th>
                      <th scope="col" rowspan=${s} class="pn" style="top:0" title=${M(`Passes of this loop`)}>${M(`Passes`)}</th>`:O}
                ${e.map((e,r)=>m(e,n[r]??0,t))}
              </tr>`})}
          </thead>
          <tbody @keydown=${e=>this.onMatrixKey(e,n)}>
            ${l>0?D`<tr class="gap" aria-hidden="true"><td colspan=${r.length+2} style="height:${l*fc}px"></td></tr>`:O}
            ${B(n.slice(l,u),e=>e.unit,(e,n)=>{let a=l+n;return D`<tr class=${e.unit&&e.unit===i?`on`:``} aria-rowindex=${a+s+1}>
                  ${e.unit?D`<th scope="row" title=${e.unit}>${e.unit}</th>`:D`<th scope="row" class="none" title=${M(`Tasks that run once per run, not once per unit`)}>${M(`No unit`)}</th>`}
                  <td class="pn ${e.passes>1?`many`:``}">${e.passes}</td>
                  ${e.cells.map((n,i)=>{let s=r[i],c=!!n&&d!==null&&d[0]===a&&d[1]===i;return D`<td class="c ${o(i)}" role="gridcell">${n&&s?this.cellMark(e,n,a,i,s.node,s.passes,c,t):O}</td>`})}
                </tr>`})}
            ${u<n.length?D`<tr class="gap" aria-hidden="true"><td colspan=${r.length+2} style="height:${(n.length-u)*fc}px"></td></tr>`:O}
          </tbody>
        </table>
      </div>
    </div></div>`}cellMark(e,t,n,r,i,a,o,s){let{name:c,parts:l}=this.markText(i.label,t,s,Lr(a.map(lo))),u=t.unit||t.key,d=nc(i.id,t,a),f=this.sel===d;return D`<button type="button" class="mark ${t.state} ${e.unit&&e.unit===this.hl?`on`:``} ${f?`sel`:``}" data-r=${n} data-c=${r} tabindex=${o?0:-1}
      title=${[c,l[0]??``].filter(Boolean).join(`
`)} aria-label=${H(c,...l)} aria-pressed=${f}
      @mouseenter=${()=>this.hover=u}
      @focus=${()=>{this.hover=u,this.cell=[n,r],this.focusSelect(d)}}
      @blur=${()=>this.hover=null}
      @click=${()=>this.select(d)}
      @dblclick=${()=>this.open(t)}></button>`}firstCell(e){for(let t=0;t<e.length;t++){let n=e[t]?.cells.findIndex(e=>e!==null)??-1;if(n>=0)return[t,n]}return null}onMatrixScroll(e){let t=Math.floor(e.currentTarget.scrollTop/fc);Math.abs(t-this.scrollRow)>=mc/2&&(this.scrollRow=t),this.anchorCard()}onMatrixKey(e,t){let n=e.target;if(!n.classList.contains(`mark`))return;let r=Number(n.dataset.r),i=Number(n.dataset.c);if(e.key===`Enter`){let n=t[r]?.cells[i];e.preventDefault(),n&&this.open(n);return}let a=Js(t.map(e=>e.cells.map(e=>e!==null)),r,i,e.key,e.ctrlKey||e.metaKey);if(!a)return;e.preventDefault(),this.cell=a;let o=this.renderRoot.querySelector(`.mx`);if(o&&t.length>pc){let e=a[0]*fc;(e<o.scrollTop+48||e>o.scrollTop+o.clientHeight-72)&&(o.scrollTop=Math.max(0,e-o.clientHeight/2)),this.scrollRow=Math.floor(o.scrollTop/fc)}this.requestUpdate(),this.updateComplete.then(()=>this.renderRoot.querySelector(`.matrix .mark[data-r="${a[0]}"][data-c="${a[1]}"]`)?.focus())}stateCounts(e){return H(...oc.filter(t=>e[t]).map(t=>this.countOf(t,e[t])))}doneOf(e){return M(j`${e.done} of ${e.total} tasks done`)}notDone(e){return[`failed`,`blocked`,`running`,`pending`,`skipped`].filter(t=>e[t]).map(t=>this.countOf(t,e[t]))}stateWord(e){return io(Vi(e),this.live)}where(e,t){let n=t?t.slice(t.lastIndexOf(`/`)+1):``;return n?`${n}:${e}`:M(j`line ${e}`)}countOf(e,t){let n=Vi(e);return J(n===`waiting`&&!this.live?`not_run`:n,t)}exceptions(e){let t=e.counts,n=[];return t.failed&&n.push([`err`,this.countOf(`failed`,t.failed)]),e.errors&&n.push([`err`,e.errors===1?M(`1 flow call stopped with an error`):M(j`${e.errors} flow calls stopped with an error`)]),t.blocked&&n.push([`warn`,this.countOf(`blocked`,t.blocked)]),t.running&&n.push([`live`,this.countOf(`running`,t.running)]),t.pending&&n.push([`mut`,this.countOf(`pending`,t.pending)]),t.skipped&&n.push([`mut`,this.countOf(`skipped`,t.skipped)]),n}neighbours(e){let t=this.graph,n=e=>{let n=t.nodes.find(t=>t.id===e);return n?n.box?M(j`${n.label} in the loop`):n.label:e},r=r=>[...t.stubs.filter(t=>t.to===e.id&&t.type===r).map(e=>e.label),...t.edges.filter(t=>t.to===e.id&&t.type===r).map(e=>n(e.from))];return{waits:r(`after`),after:r(`created`),feeds:[...new Set(t.edges.filter(t=>t.from===e.id).map(e=>n(e.to)))]}}nodeLabel(e){let t=e.counts,{waits:n,after:r,feeds:i}=this.neighbours(e);return[e.type===`flow`?H(M(j`Function ${e.label}`),this.doneOf(t)):H(e.label,this.executorWord(e),this.doneOf(t)),...this.exceptions(e).map(([,e])=>e),n.length?M(j`Waits for ${Lr(n)}`):``,r.length?M(j`Created after ${Lr(r)}`):``,i.length?M(j`Later tasks: ${Lr(i)}`):``].filter(Boolean).join(`. `)}onKey(e,t){let n=e.target;if(!n.classList.contains(`mark`)&&!n.classList.contains(`taskchip`))return;if(e.shiftKey&&e.key.startsWith(`Arrow`))return this.alongEdge(e,t);let{slots:r}=t;if(e.key===`Enter`){let t=r[Number(n.dataset.i)];e.preventDefault(),t&&this.open(t);return}let i=this.active.get(t.id)??bc(r),a={ArrowRight:1,ArrowLeft:-1,ArrowDown:t.grid.cols,ArrowUp:-t.grid.cols},o;if(e.key===`Home`)o=bc(r);else if(e.key===`End`)o=r.length-1-[...r].reverse().findIndex(e=>e!==null);else if(a[e.key]!==void 0){let t=a[e.key];for(o=i+t;o>=0&&o<r.length&&!r[o];)o+=Math.sign(t);if(o<0||o>=r.length)return}else return;e.preventDefault(),this.active.set(t.id,o),this.requestUpdate();let s=e.currentTarget;this.updateComplete.then(()=>s.querySelector(`[data-i="${o}"]`)?.focus())}alongEdge(e,t){let n=e.key===`ArrowRight`||e.key===`ArrowDown`?`later`:`earlier`,r=this.lay,i=Ys(this.graph,t.id,n,e=>{let t=r?.at[e];return t?r?.down?t.x+t.w/2:t.y+t.h/2:0});if(e.preventDefault(),!i)return;let a=this.graph.nodes.find(e=>e.id===i);if(!a)return;let o=t.slots[this.active.get(t.id)??bc(t.slots)]?.unit??``,s=Ws(a)?vc(a).filter(e=>e?.state===`failed`):vc(a),c=o?s.findIndex(e=>e?.unit===o):-1,l=c>=0?c:this.active.get(a.id)??bc(s);this.active.set(a.id,l),this.requestUpdate(),this.updateComplete.then(()=>{let e=this.renderRoot.querySelector(`.node[data-id="${CSS.escape(i)}"]`);(e?.querySelector(`[data-i="${l}"]`)??e?.querySelector(`.name`))?.focus()})}legend(){let e=this.asTable&&!this.matrix,t=(e?[]:this.matrix?this.matrix.rows.flatMap(e=>e.cells):this.graph.nodes.flatMap(e=>Ws(e)?vc(e).map(e=>e&&{...e,passes:void 0}):vc(e))).filter(e=>e!==null),n=new Set(t.map(e=>e.state)),r=!this.matrix&&t.some(e=>e.passes),i=!this.matrix&&!e&&[...this.graph.edges,...this.graph.stubs].some(e=>e.type===`created`),a=this.matrix?this.matrix.columns.map(e=>e.node):this.graph.nodes,o=new Set(a.flatMap(e=>e.executor===`mixed`?[`agent`,`python`]:e.executor?[e.executor]:[])),s=!this.matrix&&!e&&this.graph.boxes.length>0,c=!this.matrix&&(s||this.graph.nodes.some(e=>e.type===`flow`)),l=e=>Re`<svg width="22" height="8" aria-hidden="true"><path d="M1,4 H21" stroke-dasharray=${e?`5 4`:`none`}></path></svg>`;return zn([...oc.filter(e=>n.has(e)).map(e=>({label:this.stateWord(e),icon:D`<i class="mark ${e}"></i>`,decorative:!0})),...r?[{label:M(`number of passes`),icon:D`<i class="mark done" data-n="2"></i>`,decorative:!0}]:[],...o.has(`agent`)?[{label:M(`agent task`),icon:X(!1)}]:[],...o.has(`python`)?[{label:M(`Python task`),icon:X(!0)}]:[],...i?[{label:M(`waits for output`),icon:l(!1)},{label:M(`created after result`),icon:l(!0)}]:[],...s?[{label:M(`next pass`),icon:D`<svg width="24" height="12" aria-hidden="true"><path class="ret" d="M20,1.5 V5.5 Q20,9.5 16,9.5 H8 Q4,9.5 4,5.5 V5"></path>
            <path class="ret-head" d="M4,0.8 L1.4,5 L6.6,5 z"></path></svg>`}]:[],...c?[{label:M(`has an inner view`),icon:_c()}]:[]],{cls:`big`})}inspector(e){let t=this.chosen();return D`${t?Qo(this.sel,D`<section id="insp" class="insp ${this.down?`sheet`:``}" aria-label=${M(`Selected item`)}
          @keydown=${e=>this.onCardKey(e)}>
          <span class="ptr" aria-hidden="true"></span>
          <div class="scroll">${this.inspect(t,e)}</div>
        </section>`):O}<div class="sr" role="status">${this.announced}</div>`}inspect(e,t){let n=(e,t)=>D`<dt>${e}</dt><dd>${t}</dd>`,r=(e,t,n=!1)=>D`<button type="button" class="go ${n?`primary`:``}" @click=${t}>${e}</button>`,i=D`<button type="button" class="switch" @click=${()=>this.select(``)}>${M(`Clear selection`)}</button>`,a=e=>e.length?Lr(e):M(`none`,{id:`none`,desc:`An empty value`});if(e.type===`box`){let t=e.box,a=this.where(t.loop,t.file);return D`<h4 title=${t.file?`${t.file}:${t.loop}`:O}>${gc(16)}${M(j`Loop at ${a}`)}</h4>
        <dl>
          ${n(M(`Passes`),uo(t.passes))}
          ${t.spread.length>1?n(M(`Units by number of passes`),po(t.spread)):O}
        </dl>
        <div class="acts">${r(M(j`Passes of the loop at ${a}`),()=>this.primary(e),!0)}${i}</div>`}if(e.type===`node`){let t=e.node,o=t.counts,{waits:s,after:c,feeds:l}=this.neighbours(t),u=this.exceptions(t).map(([e,t])=>D`<div class=${e}>${t}</div>`);return t.type===`flow`?D`<h4 title=${t.name}>${_c()}${t.label}</h4>
          <div class="sub">${M(`Function`)}</div>
          <dl>
            ${n(M(`Flow calls`),t.calls)}
            ${n(M(`Tasks`,{id:`tasks`,desc:`A count of tasks`}),D`${this.doneOf(o)}${u}`)}
            ${n(M(`Waits for`),a(s))}
            ${c.length?n(M(`Created after`),a(c)):O}
            ${n(M(`Later tasks`),a(l))}
          </dl>
          <div class="acts">${r(M(j`Inside ${t.label}`),()=>this.primary(e),!0)}${i}</div>`:D`<h4>${t.executor&&t.executor!==`mixed`?X(t.executor===`python`):O}${t.label}</h4>
        <div class="sub">${this.executorWord(t)}</div>
        <dl>
          ${n(M(`Tasks`,{id:`tasks`,desc:`A count of tasks`}),D`${this.doneOf(o)}${u}`)}
          ${n(M(`Waits for`),a(s))}
          ${c.length?n(M(`Created after`),a(c)):O}
          ${n(M(`Later tasks`),a(l))}
        </dl>
        <div class="acts">${r(M(j`Tasks of ${t.label}`),()=>this.primary(e),!0)}${i}</div>`}let{node:o,mark:s,passes:c}=e,l=U({kind:o.label,unit:s.unit}),u=!s.flow&&s.state===`blocked`?t(s.key):``,d=D`<span data-status class=${s.state===`failed`?`err`:s.state===`blocked`?`warn`:``}>${this.stateWord(s.state)}</span>`,f=D`<h4 title=${s.flow?M(j`Flow call ${s.key}`):s.key}><i class="mark ${s.state}" aria-hidden="true"></i>${l}</h4>`,p=c.length?Lr(c.map(lo)):s.passes?fo(s.passes):``;if(s.flow){let t=s.counts;return D`${f}
        <dl>
          ${n(M(`Status`,{id:`status`,desc:`The status of a task: done, failed, not started`}),d)}
          ${p?n(M(`Pass`),p):O}
          ${t?n(M(`Tasks`,{id:`tasks`,desc:`A count of tasks`}),D`${this.doneOf(t)}${this.notDone(t).map(e=>D`<div>${e}</div>`)}`):O}
          ${s.error===void 0?O:n(M(`Error`),D`<span class="err">${s.error||M(`Flow call stopped with an error`)}</span>`)}
        </dl>
        <div class="acts">${r(M(j`Inside ${ps(s.flow)}`),()=>this.primary(e),!0)}${i}</div>`}let m=this.journal.filter(e=>s.keys.includes(e.key)).filter(K),h=m.map(e=>e.cost_usd).filter(e=>typeof e==`number`),g=m.reduce((e,t)=>e+(t.wall_s??0),0);return D`${f}
      <dl>
        ${n(M(`Status`,{id:`status`,desc:`The status of a task: done, failed, not started`}),u?D`${d}<div>${u}</div>`:d)}
        ${p?n(M(`Pass`),p):O}
        ${s.count>1?n(M(`Tasks`,{id:`tasks`,desc:`A count of tasks`}),M(j`${s.count} tasks`)):O}
        ${n(M(`Attempts`),m.length||M(`none`,{id:`none`,desc:`An empty value`}))}
        ${n(M(`Time`),m.length?P(g):M(`none`,{id:`none`,desc:`An empty value`}))}
        ${n(M(`Cost`),h.length?zr(h.reduce((e,t)=>e+t,0)):`—`)}
      </dl>
      <div class="acts">${r(M(`Task detail`),()=>this.primary(e),!0)}${o.kinds.length===1?r(M(j`Tasks of ${o.label}`),()=>this.tasksOf(o)):O}${i}</div>`}table(){let e=this.graph.nodes,t=e.some(e=>e.type===`flow`),n=[...this.graph.edges,...this.graph.stubs].some(e=>e.type===`created`),r=new Map(this.graph.boxes.map(e=>[e.id,e])),i=e=>Lr(e)||M(`none`,{id:`none`,desc:`An empty value`});return D`<div class="frame tframe" style=${!this.down&&this.layPath===this.graph.path.join(`/`)&&this.frameH>0?`height:${Math.round(this.frameH)}px`:`max-height:max(${lc}px, ${cc*100}vh)`} @scroll=${()=>this.anchorCard()}
        @click=${e=>!e.target.closest(`tbody tr`)&&this.select(``)}>
      <table class="list view">
        <thead>
          <tr>
            <th scope="col" class="fit">${M(t?`Kind or function`:`Kind`)}</th>
            <th scope="col" class="fit">${M(`Status`,{id:`status`,desc:`The status of a task: done, failed, not started`})}</th>
            <th scope="col">${M(`Waits for`)}</th>
            ${n?D`<th scope="col">${M(`Created after`)}</th>`:O}
            <th scope="col">${M(`Later tasks`)}</th>
          </tr>
        </thead>
        <tbody>
          ${B(e,e=>e.id,e=>{let t=e.counts,{waits:a,after:o,feeds:s}=this.neighbours(e),c=e.box?r.get(e.box):void 0,l=this.sel===e.id,u=e.type===`flow`?H(M(j`Function ${e.name}`),this.doneOf(t)):H(e.label,this.executorWord(e),this.doneOf(t)),d=e.type===`flow`?_c():e.executor&&e.executor!==`mixed`?X(e.executor===`python`):e.executor?D`${X(!1)}${X(!0)}`:O,f=c?M(j`Loop at ${this.where(c.loop,c.file)}`):``;return D`<tr class=${l?`sel`:``} data-id=${e.id}
                @click=${t=>!t.target.closest(`.loopchip`)&&t.detail<2&&this.select(e.id)}
                @dblclick=${t=>!t.target.closest(`.loopchip`)&&this.primary({type:`node`,id:e.id,node:e})}>
              <th scope="row" class="fit">
                <span class="nm">${d}<button type="button" class="name" title=${u} aria-pressed=${l}
                  @focus=${()=>this.focusSelect(e.id)} @keydown=${t=>this.onNameKey(t,e.id)}>${e.label}</button>${c?D`<button type="button" class="taskchip loopchip" title=${H(f,uo(c.passes))}
                      aria-label=${H(M(j`Passes of the loop at ${this.where(c.loop,c.file)}`),uo(c.passes))}
                      @click=${()=>this.go([...this.graph.path,c.id])}>${gc(12)}${uo(c.passes)}</button>`:O}</span>
              </th>
              <td class="fit st">${this.statusLine(e)}</td>
              <td class="rel">${i(a)}</td>
              ${n?D`<td class="rel">${i(o)}</td>`:O}
              <td class="rel">${i(s)}</td>
            </tr>`})}
        </tbody>
      </table>
    </div>`}statusLine(e){let t=e.counts,n=D`<span class="sep" aria-hidden="true"> | </span>`;return D`<span class="n" aria-hidden="true" title=${this.doneOf(t)}>${t.done}/${t.total}</span><span class="sr">${this.doneOf(t)}</span>${this.exceptions(e).map(([e,t])=>D`${n}<span class=${e}>${t}</span>`)}`}};V([R({attribute:!1})],Q.prototype,`plan`,void 0),V([R({attribute:!1})],Q.prototype,`journal`,void 0),V([R()],Q.prototype,`run`,void 0),V([R({type:Boolean})],Q.prototype,`live`,void 0),V([R()],Q.prototype,`layer`,void 0),V([R()],Q.prototype,`unit`,void 0),V([R()],Q.prototype,`sel`,void 0),V([z()],Q.prototype,`hover`,void 0),V([z()],Q.prototype,`asTable`,void 0),V([z()],Q.prototype,`down`,void 0),V([z()],Q.prototype,`lay`,void 0),V([z()],Q.prototype,`view`,void 0),V([z()],Q.prototype,`frameH`,void 0),V([z()],Q.prototype,`sort`,void 0),V([z()],Q.prototype,`scrollRow`,void 0),V([z()],Q.prototype,`missing`,void 0),V([z()],Q.prototype,`announced`,void 0),Q=V([L(`ca-pipeline-graph`),N()],Q);function bc(e){return Math.max(0,e.findIndex(e=>e!==null))}function xc(e,t,n){for(let r=0;r<t;r++){let i=0;for(let a of e[r]??[]){if(n>=i&&n<i+a.span&&r+a.rows>t)return!0;i+=a.span}}return!1}var Sc={failed:`✕`,attention:`◌`,done:`✓`,running:``,muted:`■`,neutral:`■`},Cc=class extends k{constructor(...e){super(...e),this.procs=null,this.plan={nodes:[],groups:[]}}static{this.styles=[I,En,w`
      :host { display: block; }
      .drv { display: flex; gap: 14px; align-items: flex-start; }
      .drv-ic { width: 42px; height: 42px; border-radius: 12px; flex: none; display: grid; place-items: center; font-size: 16px;
        background: var(--raise); color: var(--text-muted); }
      .drv.on .drv-ic { background: var(--status-running-bg); box-shadow: 0 0 0 1px color-mix(in srgb, var(--status-running) 35%, transparent), 0 0 22px var(--status-running-bg); }
      /* how a run ended: the mark's shape and the title's words carry it; the colour only where a status applies */
      .drv-ic[data-tone] { color: var(--tone); font-weight: 700; }
      .drv-ic[data-tone='failed'], .drv-ic[data-tone='attention'] { background: var(--tone-bg); }
      .drv.on .drv-ic .spin { width: 18px; height: 18px; }
      .drv-t { font-size: 15px; font-weight: 600; }
      .drv-up { font-family: var(--mono); font-size: 12px; color: var(--status-running); margin-left: 6px; font-weight: 400; }
      .drv-cmd { margin-top: 8px; }
      .drv-cmd summary { cursor: pointer; font-size: 11px; color: var(--text-muted); }
      .drv-cmd code { display: block; margin-top: 4px; white-space: pre-wrap; word-break: break-all; color: var(--text-2); max-height: 120px; overflow: auto; }
    `]}stateTitle(){if(!this.plan.nodes.length)return[M(`Not running`),`neutral`];let e=ta(this.plan);return e.failed?[M(`Finished with errors`),`failed`]:e.left?[e.left===1?M(`Finished with 1 task not done`):M(j`Finished with ${e.left} tasks not done`),`attention`]:e.notStarted?[M(`Finished with errors`),`attention`]:[M(`Finished`),`done`]}render(){let e=this.procs,t=this.summary;if(!e?.alive){let[e,n]=this.stateTitle(),r=na(t);return D`<div class="drv off">
        <div class="drv-ic" data-tone=${sn(n)} aria-hidden="true">${Sc[n]}</div>
        <div>
          <div class="drv-t tone-text" data-tone=${n===`done`?O:sn(n)}>${e}</div>
          <div class="meta">${H(t?.last_ts?M(j`Ended ${Mr(t.last_ts,!0)}`):M(`No activity`),r==null?``:M(j`Took ${P(r)}`),t?.run_group?M(j`Run group ${t.run_group}`):``)}</div>
        </div>
      </div>`}let n=Date.parse(e.started_at),r=hn.at(`drv:${e.pid??``}`,Number.isNaN(n)?1:(Date.now()-n)/1e3),i=[[M(`PID`),e.pid??`—`],[M(`Run group`),e.run_group],[M(`Running at once (limit)`),e.max_workers||`—`],[M(`Started`),Mr(e.started_at,!0)]];return D`<div class="drv on">
      <div class="drv-ic"><span class="spin"></span></div>
      <div style="min-width:0">
        <div class="drv-t">${M(`Running`)} <cae-elapsed class="drv-up" .since=${r}></cae-elapsed></div>
        <div class="drv-facts">${i.map(([e,t])=>D`<span><i>${e}</i>${t}</span>`)}</div>
        <details class="drv-cmd"><summary>${M(`Command line`)}</summary><code>${e.argv.join(` `)}</code></details>
      </div>
    </div>`}};V([R({attribute:!1})],Cc.prototype,`procs`,void 0),V([R({attribute:!1})],Cc.prototype,`summary`,void 0),V([R({attribute:!1})],Cc.prototype,`plan`,void 0),Cc=V([L(`ca-run-driver`),N()],Cc);var wc=216e5,Tc=6e4;function Ec(e,t,n){let r=[];for(let t of e){if(!t.ts)continue;let e=Date.parse(t.ts);if(Number.isNaN(e))continue;let n=K(t)?t.ok?G(t)?`py`:`llm`:`bad`:`idle`;r.push({lane:t.kind||`?`,cls:n,start:e-(t.wall_s||0)*1e3,end:e,live:!1,row:t})}if(!r.length&&!t.length)return null;for(let e of t)r.push({lane:e.kind,cls:`run`,start:e.t0,end:n,live:!0,liveCls:e.cls});let i=Math.max(...r.filter(e=>!e.live).map(e=>e.end),...t.map(e=>e.t0)),a=r.filter(e=>e.end>=i-wc),o=Math.min(...a.map(e=>e.start)),s=t.length?o+Math.ceil((n-o+2e4)/Tc)*Tc:i,c=[];for(let e of[...a].sort((e,t)=>e.start-t.start))c.includes(e.lane)||c.push(e.lane);let l=c.map(e=>{let t=a.filter(t=>t.lane===e).sort((e,t)=>e.start-t.start),n=[],r=t.map(({cls:e,start:t,end:r,live:i,row:a})=>{let o=n.findIndex(e=>e<=t);return o<0?o=n.push(r)-1:n[o]=r,a?{cls:e,start:t,end:r,live:i,track:o,row:a}:{cls:e,start:t,end:r,live:i,track:o}});return{name:e,llm:t.some(e=>e.cls===`llm`||e.liveCls===`llm`),bars:r,tracks:Math.max(1,n.length)}});return{t0:o,span:Math.max(1,s-o),lanes:l,hidden:r.length-a.length,live:t.length>0}}function Dc(e,t,n){let r=(e.start-t.t0)/t.span*100,i=((e.live?n:e.end)-e.start)/t.span*100;return{left:r,width:Math.max(.4,e.live?Math.min(100-r,i):i)}}var Oc=e=>new Date(e).toLocaleTimeString(en(),{hour:`2-digit`,minute:`2-digit`,hourCycle:`h23`}),kc=e=>new Date(e).toLocaleTimeString(en(),{hour:`2-digit`,minute:`2-digit`,second:`2-digit`,hourCycle:`h23`}),Ac=6e5,jc=class extends k{constructor(...e){super(...e),this.journal=[],this.plan=null,this.procs=null,this.live=!1,this.run=``,this.drawnRun=null,this.timer=null}static{this.styles=[I,Bn,w`
      :host { display: block; }
      .tl { position: relative; }
      .tl-axis { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 10px; color: var(--text-muted); margin: 0 0 6px 120px; }
      .tl-row { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 8px; align-items: center; min-height: 24px; padding: 4px 0; }
      .nm { font-size: 11.5px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .tl-lane { position: relative; height: calc(var(--tracks, 1) * 14px + 2px); border-radius: 4px;
        background: repeating-linear-gradient(90deg, color-mix(in srgb, var(--text) 5%, transparent) 0 1px, transparent 1px 10%); }
      .tl-bar { position: absolute; top: calc(var(--track, 0) * 14px + 2px); height: 12px; border-radius: 4px; min-width: 3px; cursor: default;
        transform-origin: left center; transition: width 1s linear; }
      .tl.anim .tl-bar:not(.run) { animation: growx 0.6s var(--ease) both; }
      /* who ran it is an identity cue (Python neutral, an agent violet); failed and running are statuses,
         each with a pattern of its own besides the colour (failed: fine hatching; running: moving stripes) */
      .tl-bar.py, .legend i.py { background: var(--meter); }
      .tl-bar.llm, .legend i.llm { background: var(--agent); }
      .tl-bar.bad, .legend i.bad { background: repeating-linear-gradient(135deg, var(--status-failed) 0 3px,
        color-mix(in srgb, var(--status-failed) 55%, var(--bg)) 3px 5px); }
      .tl-bar.idle, .legend i.idle { background: none; box-shadow: inset 0 0 0 1.5px var(--line2); }
      .tl-bar.run, .legend i.run { background: repeating-linear-gradient(45deg, var(--status-running) 0 6px,
        color-mix(in srgb, var(--status-running) 60%, var(--bg)) 6px 12px); background-size: 17px 17px; }
      .tl-bar.run { animation: stripes 0.8s linear infinite; box-shadow: 0 0 12px color-mix(in srgb, var(--status-running) 45%, transparent); }
      .tl-bar:hover { filter: brightness(1.2); }
      .tl-now { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--status-running); border-radius: 2px; box-shadow: 0 0 10px var(--status-running); }
      .legend { margin-top: 10px; }
      .legend + .legend { margin-top: 4px; }
      @media (max-width: 760px) {
        .tl-row { grid-template-columns: 78px minmax(0, 1fr); }
        .tl-axis { margin-left: 86px; }
      }
    `]}updated(e){e.has(`live`)&&this.tick(this.live)}connectedCallback(){super.connectedCallback(),this.tick(this.live)}disconnectedCallback(){super.disconnectedCallback(),this.tick(!1)}tick(e){e&&!this.timer&&(this.timer=setInterval(()=>this.requestUpdate(),1e3)),!e&&this.timer&&(clearInterval(this.timer),this.timer=null)}render(){let e=Date.now(),t=this.live?Fi(this.procs).map(t=>({kind:t.kind,cls:t.cls,t0:hn.at(t.id,t.ageS,e)})):[],n=Ec(this.journal,t,e);if(!n)return D`<div class="blank" style="padding:28px"><span class="ic" aria-hidden="true">⏱</span>${this.live?M(`No finished attempts yet`):M(`No finished attempts`)}</div>`;let r=this.drawnRun!==this.run;this.drawnRun=this.run;let{outcomes:i}=Zi(this.journal,this.plan),a=(e,t)=>{let n=t.row;if(!n)return`${e}\n${M(`running`)}`;if(!K(n)){let e=i.get(n.key),t=n.stop===`invalid_input`&&e?va(e,i,this.run):``;return[U(n),t?M(j`Not started: ${t}`):Y(n.stop,n.reason),n.key].join(`
`)}let r=vo(n.hops),a=n.reason&&!n.ok?q(n.reason,this.run):``;return[U(n),H(Y(n.stop),P(n.wall_s),M(j`ended ${kc(t.end)}`)),r?M(j`Model switch: ${r}`):n.model?M(j`Model ${n.model}`):``,a,n.key].filter(Boolean).join(`
`)},o=Math.min(1,(e-n.t0)/n.span),s=n.span<Ac?kc:Oc;return D`<div class="tl ${r?`anim`:``}">
        <div class="tl-axis">${[0,.25,.5,.75,1].map(e=>D`<span>${s(n.t0+n.span*e)}</span>`)}</div>
        ${B(n.lanes,e=>e.name,t=>D`<div class="tl-row">
            <span class="nm" title=${t.name}>${t.name}</span>
            <div class="tl-lane" style="--tracks:${t.tracks}">
              ${t.bars.map(r=>{let i=Dc(r,n,e);return D`<span class="tl-bar ${r.cls}" style="--track:${r.track};left:${i.left.toFixed(3)}%;width:${i.width.toFixed(3)}%" title=${a(t.name,r)}></span>`})}
            </div>
          </div>`)}
        ${n.live?D`<span class="tl-now" style="left:calc(120px + (100% - 120px) * ${o.toFixed(4)})"></span>`:O}
      </div>
      ${zn([{label:M(`Python task`),cls:`py`},{label:M(`Agent task`),cls:`llm`}])}
      ${zn([{label:M(`running`),cls:`run`},{label:M(`failed`),cls:`bad`},{label:M(`not started`),cls:`idle`},...n.hidden?[{label:n.hidden===1?M(`1 older attempt not shown`):M(j`${n.hidden} older attempts not shown`)}]:[]])}`}};V([R({attribute:!1})],jc.prototype,`journal`,void 0),V([R({attribute:!1})],jc.prototype,`plan`,void 0),V([R({attribute:!1})],jc.prototype,`procs`,void 0),V([R({type:Boolean})],jc.prototype,`live`,void 0),V([R()],jc.prototype,`run`,void 0),jc=V([L(`ca-timeline`),N()],jc);var Mc=class extends k{constructor(...e){super(...e),this.procs=null,this.live=!1}static{this.styles=[I,w`
      :host { display: block; }
      .wks { display: grid; grid-template-columns: repeat(var(--n, 3), minmax(0, 1fr)); gap: 10px; }
      @media (max-width: 900px) { .wks { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      .wk { border-radius: 11px; padding: 10px 12px; border: 1px solid var(--line); background: color-mix(in srgb, var(--text) 2.5%, transparent); min-width: 0;
        position: relative; overflow: hidden; }
      .wk.py, .wk.llm { border-color: var(--line2); }
      .wk.llm { box-shadow: inset 3px 0 0 -1px color-mix(in srgb, var(--agent) 60%, transparent); cursor: pointer; }
      .wk.llm:hover { border-color: var(--accent); }
      .wk.idle { opacity: 0.45; border-style: dashed; }
      .wk-top { display: flex; align-items: center; gap: 8px; min-width: 0; }
      .wk-top b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .wk-ic { width: 24px; height: 24px; border-radius: 7px; flex: none; display: grid; place-items: center; background: var(--raise); font-size: 12px; }
      .wk.llm .wk-ic { color: var(--agent); }
      .wk.py .wk-ic { color: var(--text-muted); }
      .wk-el { margin-left: auto; font-family: var(--mono); font-size: 11.5px; color: var(--status-running); }
      .wk-bar { position: absolute; left: 0; right: 0; bottom: 0; height: 2px; overflow: hidden; }
      .wk-bar i { position: absolute; top: 0; bottom: 0; width: 30%; background: linear-gradient(90deg, transparent, var(--status-running), transparent);
        animation: scan 1.8s linear infinite; }
    `]}render(){let e=this.live?Fi(this.procs):[],t=Math.max(this.procs?.max_workers||1,e.length),n=Array.from({length:t-e.length},(e,t)=>t);return D`<div class="wks" style="--n:${Math.min(t,6)}">
      ${B(e,e=>e.id,e=>D`<div class="wk ${e.cls}"
          @click=${e.key?()=>A(this,`ca-open-task`,{key:e.key}):O}>
          <div class="wk-top">${X(e.cls!==`llm`,e.cls===`llm`?M(`Agent task`):M(`Python task`),`wk-ic`)}<b>${e.kind}</b>
            <cae-elapsed class="wk-el" .since=${hn.at(e.id,e.ageS)}></cae-elapsed></div>
          <div class="meta">${e.detail}</div>
          <div class="wk-bar"><i></i></div>
        </div>`)}
      ${n.map(()=>D`<div class="wk idle"><div class="wk-top"><b>${M(`Idle`)}</b></div>
          <div class="meta">${M(`No task`)}</div></div>`)}
    </div>`}};V([R({attribute:!1})],Mc.prototype,`procs`,void 0),V([R({type:Boolean})],Mc.prototype,`live`,void 0),Mc=V([L(`ca-workers`),N()],Mc);var Nc=5,Pc=[`invalid`,`refused`,`failed`,`running`,`pending`,`valid`];function Fc(e){if(e===void 0)return M(`Loading…`);if(typeof e!=`object`||!e)return JSON.stringify(e);let t=Object.keys(e);if(!t.length)return M(`Empty`);let n=`${t.slice(0,4).join(`, `)}${t.length>4?`, …`:``}`;return M(Array.isArray(e)?j`${t.length} items: ${n}`:j`${t.length} keys: ${n}`)}var Ic=class extends k{constructor(...e){super(...e),this.run=``,this.layer=``,this.unit=``,this.sel=``}static{this.styles=[I,w`
      :host { display: block; }
      .ct-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
      .pcards { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(320px, 100%), 1fr)); gap: 12px; }
      .pcard { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 12px; align-items: start; padding: 12px 14px; border-radius: 10px;
        background: var(--raise); border: 1px solid var(--line); cursor: pointer; transition: border-color 0.15s, transform 0.15s;
        text-align: left; color: inherit; font: inherit; width: 100%; min-width: 0; }
      .pcard > div { min-width: 0; }
      .pcard .meta { overflow-wrap: anywhere; }
      .pcard:hover { border-color: var(--accent); transform: translateY(-1px); }
      .pc-ic { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 9px; background: var(--well); color: var(--text-2); font-size: 16px; }
      .pc-peek { font-family: var(--mono); font-size: 11.5px; color: var(--text-2); margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .pc-go { grid-column: 2; color: var(--accent); font-size: 12px; opacity: 0.8; margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .pcard:hover .pc-go { opacity: 1; }
      .cur-units { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px 14px; }
      .cu { display: grid; grid-template-columns: 90px 1fr 70px auto; gap: 8px; align-items: center; }
      .cu-bar { height: 5px; border-radius: 3px; background: var(--track); overflow: hidden; }
      .cu-bar i { display: block; height: 100%; background: var(--meter); }
      .fl > div.meta { grid-column: 1 / 4; overflow: hidden; text-overflow: ellipsis; }
      .stopped { grid-column: 1 / 4; color: var(--text-muted); font-size: 11px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
      .fl.muted { opacity: 0.7; }
      .next { margin: 10px 2px 2px; font-size: 12px; color: var(--text-2); }
      .next code { font-family: var(--mono); }
      .more { font-size: 12px; margin: 6px 10px 0; }
    `]}go(e){A(this,`ca-navigate`,{tab:e})}open(e){A(this,`ca-open-task`,{key:e.key,...G(e)?{view:`output`}:{}})}render(){let e=this.state,t=Pi(e,this.summary),n=t?Fi(e.procs).length:0,r=e.procs?.max_workers||1,i=this.info.panels;return D`<div class="g12">
      <section class="panel c5 enter">
        <h3>${M(`Run`)}</h3>
        <ca-run-driver .procs=${e.procs} .summary=${this.summary} .plan=${e.plan}></ca-run-driver>
      </section>
      <section class="panel c7 enter">
        <h3 title=${M(`Limit: max_concurrent`)}>${M(`Running tasks`)}
          ${t?D`<span class="r">${M(j`${n} of ${r} running at once`)}</span>`:O}</h3>
        ${t?D`<ca-workers .procs=${e.procs} .live=${t}></ca-workers>`:D`<div class="meta">${M(`No tasks running`)}</div>`}
      </section>
      <section class="panel c12 enter">
        <h3 title=${M(`Every task the run scheduled, by kind (plan.jsonl)`)}>${M(`Pipeline`)}
          <span class="r">${this.progressLine(t)}</span></h3>
        <ca-pipeline-graph .plan=${e.plan} .journal=${e.journal} .run=${this.run} .layer=${this.layer} .unit=${this.unit} .sel=${this.sel} ?live=${t}></ca-pipeline-graph>
      </section>
      <section class="panel c12 enter">
        <h3 title=${M(`Counted from every finished attempt (journal.jsonl)`)}>${M(`Totals`)}</h3>
        <ca-kpis .journal=${e.journal} .plan=${e.plan}></ca-kpis>
      </section>
      ${oa(e.journal)?D`<section class="panel c12 enter">
            <h3 title=${M(`Reported by the coding agents`)}>${M(`Tokens and cost by kind`)}</h3>
            <ca-spend-breakdown .journal=${e.journal}></ca-spend-breakdown>
          </section>`:O}
      ${pa(e.journal).length?D`<section class="panel c12 enter">
            <h3 title=${M(`Reported at each agent session start. Account-wide: every task that runs at once shares it.`)}>
              ${M(`Subscription usage`)}<span class="r">${M(`Per account, first → last reading`)}</span></h3>
            <ca-quota .journal=${e.journal}></ca-quota>
          </section>`:O}
      <section class="panel ${t?`c5`:`c12`} enter">
        <h3>${M(`Problems`)}
          <span class="r"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>A(this,`ca-navigate`,{tab:`journal`,stop:`bad`}))}>${M(`Failed attempts in history`)}</a></span></h3>
        ${this.problems(t)}
      </section>
      ${t?D`<section class="panel c7 enter">
            <h3>${M(`Process tree`)}
              <span class="r"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>this.go(`procs`))}>${M(`All processes`)}</a></span></h3>
            <ca-proc-tree .procs=${e.procs}></ca-proc-tree>
          </section>`:O}
      <section class="panel c12 enter">
        <h3 title=${M(`Checked files (OutputContract, InputContract)`)}>${M(`Outputs`)}
          <span class="r"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>this.go(`outputs`))}>${M(`All outputs`)}</a></span></h3>
        ${this.outputs()}
      </section>
      ${e.cursor?D`<section class="panel c12 enter">
            <h3 title=${M(`Stage and step per unit (CursorStore)`)}>${M(`Resume cursor`)}</h3>
            ${this.cursor()}
          </section>`:O}
      ${i.length?D`<section class="panel c12 enter">
            <h3 title=${M(`monitor.Panel`)}>${M(`Custom views`)}</h3>
            ${this.panelCards()}
          </section>`:O}
      <section class="panel c12 enter">
        <h3>${M(`Timeline`)}
          <span class="r">${this.triesLine()}</span></h3>
        <ca-timeline .journal=${e.journal} .plan=${e.plan} .procs=${e.procs} .live=${t} .run=${this.run}></ca-timeline>
      </section>
    </div>`}outputs(){let{contracts:e,tally:t}=this.state.outputs;if(!e.length)return D`<div class="meta">${M(`No output files`)}</div>`;let n=Pc.filter(e=>t[e]),r=e.flatMap(e=>(e.outputs??[]).map(t=>[e,t])).filter(([,e])=>e.status===`invalid`||e.status===`failed`),i=r.slice(0,Nc),a=t.refused;return D`<div class="ct-row">
        ${n.length?n.map(e=>Pa(e,t[e])):D`<span class="meta">${M(`No checked files`)}</span>`}
      </div>
      ${i.map(([e,t])=>D`<div class="fl" @click=${()=>this.go(`outputs`)}>
          ${An({text:t.status?ya(t.status):`—`,tone:Aa(t.status),title:t.status?ba(t.status):null})}
          <b class="jmono" title=${e.key}>${U({kind:e.kind,unit:e.unit===e.key?``:e.unit})}</b>
          <span class="meta">${Ua(t)}</span>
          <div class="meta">${q(t.errors?.[0]||t.path,this.run).slice(0,160)}</div>
        </div>`)}
      ${r.length>i.length?D`<div class="more"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>this.go(`outputs`))}>${r.length-i.length===1?M(`1 more output`):M(j`${r.length-i.length} more outputs`)}</a></div>`:O}
      ${a?D`<div class="meta more">${M(a===1?`1 output not written (task not started)`:j`${a} outputs not written (tasks not started)`)}</div>`:O}`}progressLine(e){let t=this.state.plan,n=ta(t);if(e||n.left){let e=ea(t);return H(M(j`${e.pct}%`),M(j`${e.done} of ${e.total} tasks done`),e.skipped?J(`skipped`,e.skipped):``)}return H(J(`done`,n.done),n.skipped?J(`skipped`,n.skipped):``,n.failed?J(`failed`,n.failed):``,n.notStarted?J(`not_started`,n.notStarted):``)}triesLine(){let{tries:e,notStarted:t}=Zi(this.state.journal,this.state.plan).tries;return H(M(e===1?`1 attempt`:j`${e} attempts`),t?J(`not_started`,t):``)}nav(e,t){e.preventDefault(),t()}cursor(){let e=this.state.cursor,t=Object.entries(e?.units??{});if(!e||!e.stage&&!t.length)return D`<div class="meta">${M(`No resume cursor`)}</div>`;let n=e.completed_stages??[];return D`<div class="chips" style="margin-bottom:10px">
        ${n.length||e.stage?D`${n.map(e=>D`<span class="chip" data-tone="done"><span aria-hidden="true">✓</span><span class="sr">${M(`done`,{id:`stage-done`,desc:`A stage of the resume cursor that is complete`})}</span> ${e}</span>`)}${e.stage?D`<span class="chip" data-tone="running"><span class="sr">${M(`current`)}</span>${e.stage}</span>`:O}`:D`<span class="meta">${M(`No stage`)}</span>`}
      </div>
      ${t.length?D`<div class="cur-units">
            ${t.map(([e,t])=>D`<div class="cu">
                <span class="jmono">${e}</span>
                <span class="meta">${H(t.step||`—`,t.loop_pass?M(j`loop pass ${t.loop_pass}`):``)}</span>
                <span class="cu-bar" title=${t.completed.length===1?M(`1 step completed`):M(j`${t.completed.length} steps completed`)}><i style="width:${Math.min(100,12*(t.completed.length+1))}%"></i></span>
                ${t.inflight.length?kn({text:M(`running`),tone:`running`,title:t.inflight.join(`
`)}):O}
              </div>`)}
          </div>`:O}`}panelCards(){return D`<div class="pcards">
      ${B(this.info.panels,e=>e.name,e=>D`<button type="button" class="pcard" @click=${()=>this.go(`panel:${e.name}`)}>
          <span class="pc-ic" aria-hidden="true">${e.icon||`▤`}</span>
          <div>
            <b>${e.title||e.name}</b>
            ${e.description?D`<div class="meta">${e.description}</div>`:O}
            <div class="pc-peek">${Fc(this.state.panels[e.name])}</div>
          </div>
          <span class="pc-go">${M(j`Show ${e.title||e.name}`)}</span>
        </button>`)}
    </div>`}name(e){return U(e)}problems(e){let{outcomes:t,problems:n}=Zi(this.state.journal,this.state.plan),{failed:r,notStarted:i,recovered:a}=n;if(!r.length&&!i.length&&!a.length)return D`<div class="blank" style="padding:22px"><span class="ic" aria-hidden="true">✓</span>${M(`No problems`)}</div>`;let o=e=>q(e.attempts[e.attempts.length-1]?.reason||`—`,this.run).slice(0,200),s=e=>e.length?D`<div class="stopped">
            <span>${e.length===1?M(`1 later task not started`):M(j`${e.length} later tasks not started`)}</span>
            ${e.map(e=>Bo(this,this.name(e),e))}
          </div>`:O;return D`${B(r,e=>e.task.key,e=>{let t=e.task.attempts[e.task.attempts.length-1];return D`<div class="fl" @click=${()=>this.open(e.task)}>
            ${An({text:ro(`failed`),tone:`failed`})}
            <b class="jmono" title=${e.task.key}>${this.name(e.task)}</b><span class="meta">${Mr(t?.ts,!0)}</span>
            <div class="meta">${Y(t?.stop)}: ${o(e.task)}</div>
            ${s(e.stopped)}
          </div>`})}
      ${B(i,e=>e.key,e=>D`<div class="fl" @click=${()=>this.open(e)}>
          ${An({text:ro(`not_started`),tone:`attention`})}
          <b class="jmono" title=${e.key}>${this.name(e)}</b><span></span>
          <div class="meta">${va(e,t,this.run)?Pr(va(e,t,this.run)):o(e)}</div>
        </div>`)}
      ${B(a,e=>e.key,e=>{let t=e.tries.filter(e=>!e.ok).length,n=e.tries.length,r=this.name(e);return D`<div class="fl muted" @click=${()=>this.open(e)}>
            ${An({text:ro(`recovered`),tone:ka(`recovered`)})}
            <b class="jmono" title=${e.key}>${r}</b><span></span>
            <div class="meta">${M(t===1?j`Done on attempt ${n} after 1 failed attempt`:j`Done on attempt ${n} after ${t} failed attempts`)}</div>
          </div>`})}
      ${this.nextStep(e,r.length+i.length)}`}nextStep(e,t){if(e||!t)return O;let n=Zi(this.state.journal,this.state.plan).counts,r=n.total-n.finished;return r?D`<div class="next" title="resume=True">${M(j`${r} of ${n.total} tasks not done`)}</div>`:O}};V([R({attribute:!1})],Ic.prototype,`state`,void 0),V([R({attribute:!1})],Ic.prototype,`summary`,void 0),V([R({attribute:!1})],Ic.prototype,`info`,void 0),V([R()],Ic.prototype,`run`,void 0),V([R()],Ic.prototype,`layer`,void 0),V([R()],Ic.prototype,`unit`,void 0),V([R()],Ic.prototype,`sel`,void 0),Ic=V([L(`ca-overview`),N()],Ic);function Lc(e,t,n){let r=n.toLowerCase();return e.filter(e=>(!t||e.kind===t)&&(!r||`${e.kind} ${e.unit} ${e.key} ${e.last_stop}`.toLowerCase().includes(r)))}var Rc={failed:0,not_started:1,running:2,waiting:3};function zc(e){return e.map((e,t)=>({t:e,i:t})).sort((e,t)=>(Rc[e.t.outcome]??9)-(Rc[t.t.outcome]??9)||t.t.last_ts.localeCompare(e.t.last_ts)||e.i-t.i).map(e=>e.t)}var Bc=[`key`,`unit`,`stop`,`kind`,`route`,`reason`],Vc=e=>new Set(Bi(e).map(e=>e.key)),Hc=e=>(e.rounds??1)>1;function Uc(e,t,n,r){let i=r.toLowerCase(),a=n===`retried`?Vc(e):null;return e.filter(e=>n===`bad`&&!Ai(e)||n===`fixup`&&!Hc(e)||a&&!a.has(e.key)||n&&![`bad`,`fixup`,`retried`].includes(n)&&e.stop!==n||t&&e.kind!==t?!1:!i||Bc.some(t=>String(e[t]??``).toLowerCase().includes(i)))}function Wc(e){let t=new Map;for(let n of e)t.set(n.stop||`?`,(t.get(n.stop||`?`)??0)+1);return[...t.entries()].sort((e,t)=>t[1]-e[1])}function Gc(e){let t=new Map;return e.forEach((e,n)=>{let r=t.get(e.key)??{count:0,lastOk:-1,lastOkTry:0};K(e)&&r.count++,e.ok&&(r.lastOk=n,r.lastOkTry=(e.attempt??0)+1),t.set(e.key,r)}),t}var Kc=class extends k{constructor(...e){super(...e),this.journal=[],this.plan=null,this.kind=``,this.q=``,this.live=!1,this.run=``}static{this.styles=[I,es,Tn,w`
      :host { display: block; margin-top: 4px; }
      /* the numbers sit tight together, right-aligned; the outcome comes last and takes the spare width, so no gap opens inside the row */
      .trow { display: grid; grid-template-columns: minmax(220px, 0.6fr) 64px 132px 72px 72px 128px minmax(240px, 1fr);
        column-gap: 20px; padding: 6px 12px; align-items: center; border-radius: 8px; transition: background 0.15s; cursor: pointer; }
      .trow.hd { cursor: default; }
      .trow:not(.hd):hover { background: var(--raise); }
      .trow.running { background: var(--status-running-bg); }
      .trow.hd { align-items: end; white-space: nowrap; padding: 4px 12px 8px; color: var(--text-muted); font-size: 11px; border-bottom: 1px solid var(--line); border-radius: 0; margin-bottom: 4px; }
      .num { text-align: right; font-variant-numeric: tabular-nums; }
      .wall { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
      .wall .jdur { width: 56px; margin: 0; flex: none; }
      .grow { display: flex; align-items: center; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .grow .jdim { margin-left: 8px; }
      .pass { margin-left: 8px; font-size: 11px; color: var(--text-muted); }
      .cause { display: block; font-size: 11px; color: var(--text-muted); margin-top: 2px; white-space: normal; overflow-wrap: anywhere; }
      @media (max-width: 760px) {
        .trow { grid-template-columns: minmax(0, 1fr) 128px 90px; }
        .trow > span:nth-child(2), .trow > span:nth-child(4), .trow > span:nth-child(5), .trow > span:nth-child(6) { display: none; }
      }
    `]}cause(e,t){return e.outcome===`not_started`?va(e,t,this.run):e.outcome===`waiting`?ga(e.waits_for.map(e=>t.get(e)??{kind:e})):``}spendCells(e,t){return e?t?.reported?D`<span class="num" title=${H(M(j`Cache read ${W(t.cache_read)}`),M(j`Cache write ${W(t.cache_creation)}`))}>${W(t.input+t.output)}</span><span class="num">${zr(t.cost)}</span>`:D`<span class="num jdim">—</span><span class="num jdim">—</span>`:D`<span class="num jdim">${M(`none`,{id:`none`,desc:`An empty value`})}</span><span class="num jdim">${M(`none`,{id:`none`,desc:`An empty value`})}</span>`}render(){let e=this.plan?Zi(this.journal,this.plan):null,t=e?.rows??[],n=zc(Lc(t,this.kind,this.q));if(!n.length)return D`<div class="blank"><span class="ic" aria-hidden="true">≡</span>${t.length?M(`No tasks match the filter`):M(`No tasks`)}</div>`;let r=e?.outcomes??new Map,i=new Map;for(let e of t)i.set(`${e.kind}|${e.unit}`,(i.get(`${e.kind}|${e.unit}`)??0)+1);let a=Math.max(1,...n.map(e=>e.wall_s)),o=new Map;for(let e of this.journal)aa(o.get(e.key)??o.set(e.key,ra()).get(e.key),e);return D`<div class="trow hd">
        <span title=${M(`Kind · unit`)}>${M(`Task`)}</span><span class="num" title=${M(`Attempts that ran`)}>${M(`Attempts`)}</span>
        <span class="num" title=${M(`Sum over all attempts`)}>${M(`Time`)}</span>
        <span class="num" title=${M(`Input and output tokens, all attempts`)}>${M(`Tokens`)}</span>
        <span class="num" title=${M(`Reported by the coding agent`)}>${M(`Cost`)}</span>
        <span class="num">${M(`Last attempt ended`)}</span>
        <span class="st">${M(`Status`,{id:`status`,desc:`The status of a task: done, failed, not started`})}</span>
      </div>
      ${B(n,e=>e.key,e=>{let t=G(e),n=e.outcome===`running`,s=e.tries.length>0,c=this.cause(e,r),l=e.pass!==null&&(i.get(`${e.kind}|${e.unit}`)??0)>1?e.pass:null;return D`<div class="trow ${n?`running`:``} ${t?`py`:``}"
            @click=${()=>A(this,`ca-open-task`,t?{key:e.key,view:`output`}:{key:e.key})}>
            <span class="grow jmono" title=${e.key}>
              ${X(t,M(t?`Python task`:`Agent task`))}${e.kind}
              ${e.unit?D`<span class="jdim">· ${e.unit}</span>`:O}${l===null?O:D`<span class="pass">${lo(l)}</span>`}
            </span>
            <span class="num">${e.tries.length}</span>
            <span class="num wall">${s?D`${P(e.wall_s)}<span class="jdur"><i class=${t?``:`llm`}
                  style="width:${Math.max(4,Math.round(100*e.wall_s/a))}%"></i></span>`:D`<span class="jdim">${M(`none`,{id:`none`,desc:`An empty value`})}</span><span class="jdur" style="visibility:hidden"></span>`}</span>
            ${this.spendCells(s,o.get(e.key))}
            <span class="num meta">${s?Mr(e.tries[e.tries.length-1]?.ts,!0):M(`none`,{id:`none`,desc:`An empty value`})}</span>
            <span class="st">${kn({text:io(e.outcome,this.live),tone:ka(e.outcome),mark:ja(e.outcome),title:e.last_stop})}${c?D`<span class="cause">${c}</span>`:O}</span>
          </div>`})}`}};V([R({attribute:!1})],Kc.prototype,`journal`,void 0),V([R({attribute:!1})],Kc.prototype,`plan`,void 0),V([R()],Kc.prototype,`kind`,void 0),V([R()],Kc.prototype,`q`,void 0),V([R({type:Boolean})],Kc.prototype,`live`,void 0),V([R()],Kc.prototype,`run`,void 0),Kc=V([L(`ca-task-table`),N()],Kc);var qc=`grid-template-columns:64px minmax(130px,0.8fr) minmax(150px,0.7fr) minmax(150px,1fr) 92px 60px 76px minmax(200px,2.2fr)`,Jc=class extends k{constructor(...e){super(...e),this.rows=[],this.plan=null,this.fresh=new Set,this.kind=``,this.stop=``,this.q=``,this.run=``,this.outcomes=new Map}static{this.styles=[I,Tn,w`
      :host { display: block; }
      .jtally { display: flex; flex-wrap: wrap; gap: 8px; padding: 2px 0 12px; }
      .jchip { border: 1px solid var(--line); border-radius: 999px; padding: 3px 11px; font-size: 11.5px; color: var(--text-muted);
        cursor: pointer; transition: all 0.15s; background: none; }
      .jchip b { color: var(--text); }
      .jchip:hover { border-color: var(--line2); color: var(--text); }
      .jchip.on { background: var(--accent-bg); border-color: var(--accent); color: var(--text); }
      /* a stop's chip: marked by its status (data-mark: done quiet with a ✓, a failure red with a ✕, not started ◌) */
      .jchip[data-tone='failed'], .jchip[data-tone='attention'] { color: var(--tone); border-color: color-mix(in srgb, var(--tone) 40%, transparent); }
      .table { overflow-x: auto; }
      .jrow { display: grid; column-gap: 12px; row-gap: 2px; padding: 7px 12px; border-bottom: 1px solid var(--line); font-size: 12px; align-items: center; min-width: 980px; }
      .jrow > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
      .jrow > span.jstop { white-space: normal; }
      .jrow:hover { background: var(--card); }
      .jrow.hd { color: var(--text-muted); font-size: 11px; position: sticky; top: 0; background: var(--bg); z-index: 1; }
      .jrow.bad { background: color-mix(in srgb, var(--status-failed) 6%, transparent); box-shadow: inset 3px 0 0 var(--status-failed); }
      .jrow.py { opacity: 0.85; }
      .jrow.py:hover, .jrow.py.bad { opacity: 1; }
      .jrow.fresh { animation: rowin 1.6s var(--ease); }
      .jrow.agent { cursor: pointer; }
      .num { text-align: right; font-variant-numeric: tabular-nums; }
      .jwhy { color: var(--text-2); white-space: normal !important; overflow-wrap: anywhere; }
      .later { color: var(--status-done); }
      .nw { white-space: nowrap; }
      .jrow.notrun { opacity: 0.8; }
      .unread { color: var(--status-attention); }
      .two { display: flex; flex-direction: column; line-height: 1.35; }
      /* the status mark stays beside its word, the lines under it align with the word */
      .jstop.two { display: grid; grid-template-columns: auto minmax(0, 1fr); align-content: center; }
      .jstop.two > * { grid-column: 2; }
      .jstop.two::before { grid-row: 1; }
      .two .sub { color: var(--text-muted); font-size: 11px; white-space: normal; overflow-wrap: anywhere; }
      .num.two > span { white-space: nowrap; }
      .jrow > span.two { white-space: normal; }
      .sub .q { color: var(--text-2); font-family: var(--mono); white-space: nowrap; }
      .jstop .sub { font-weight: 400; }
      .cost { font-variant-numeric: tabular-nums; text-align: right; color: var(--text-2); }
    `]}render(){this.outcomes=Zi(this.rows,this.plan).outcomes;let e=Uc(this.rows,this.kind,this.stop,this.q).reverse(),t=Math.max(1,...e.map(e=>e.wall_s||0)),n=Gc(this.rows),r=new Map(this.rows.map((e,t)=>[e,t])),i=this.rows.filter(Hc).length,a=Vc(this.rows).size,o=(e,t,n,r,i=`neutral`)=>D`<button type="button" class="jchip ${this.stop===e?`on`:``}" data-tone=${sn(i)} data-mark=${Dn(i)??O}
        aria-pressed=${this.stop===e} title=${r}
        @click=${()=>A(this,`ca-filter`,{stop:this.stop===e?``:e})}>${t} <b>${n}</b></button>`;return D`<div class="jtally">
        ${Wc(this.rows).map(([e,t])=>o(e,this.shortStop(e),t,e,Oa(e)))}
        ${i?o(`fixup`,M(`attempts with corrections`),i,M(`Attempts with at least one correction`)):O}
        ${a?o(`retried`,M(`tasks retried`),a,M(`Tasks retried after a failed attempt`)):O}
      </div>
      <div class="table">
      <div class="jrow hd" style=${qc}>
        <span>${M(`Ended`)}</span><span>${M(`Task`)}</span>
        <span title=${M(`How the attempt ended (stop)`)}>${M(`Outcome`)}</span>
        <span>${M(`Agent, model, identity`)}</span>
        <span class="num" title=${M(`Input / output tokens, then cache read / cache write`)}>${M(`Tokens`)}</span>
        <span class="num" title=${M(`Reported by the coding agent`)}>${M(`Cost`)}</span>
        <span class="num">${M(`Time`)}</span><span>${M(`Reason`)}</span>
      </div>
      ${B(e,Mi,e=>{let i=n.get(e.key),a=!e.ok&&K(e)&&(i?.lastOk??-1)>(r.get(e)??0)?i?.lastOkTry??0:0;return this.row(e,t,(i?.count??1)>1,a)})}
      </div>
      ${e.length?O:D`<div class="meta" style="padding:8px">${M(`No finished attempts`)}</div>`}`}shortStop(e){return e===`invalid_input`?ro(`not_started`):Y(e)}reason(e,t,n){let r=vo(e.hops),i=this.run||e.run_id||``,a=this.outcomes.get(e.key),o=e.stop===`invalid_input`&&a?va({attempts:[e],cause:null},this.outcomes,i):``,s=o?Pr(o):(!e.ok||!t)&&e.reason?q(e.reason,i):``,c=n?M(j`The task was done on attempt ${n}`):``;return!r&&!s&&!c?D`<span class="jdim">—</span>`:D`${r?D`<span class="nw" title=${M(`Model switch`)}>${r}</span><br />`:O}${s?D`${s}<br />`:O}${c?D`<span class="later">${c}</span>`:O}`}identity(e){let t=[...new Set([...(e.hops??[]).map(e=>e.credential),e.credential].filter(Boolean))];if(!t.length)return O;let n=(e.quota??[])[0],r=n?M(j`Usage at session start (account-wide): ${wo(n)}`):``,i=n&&t.length===1&&(n.credential??``)===t[0],a=n?i?So(n):wo(n):``;return D`<span class="sub" title=${[r,...t.map(go)].filter(Boolean).join(`
`)||O}>${t.map(e=>ho(e)).join(` → `)}${n?D` <span class="q">${a}</span>`:O}</span>`}spend(e){let t=e.usage,n=e.hops??[],r=n.length>1?n.map(e=>H(e.model||e.route||`—`,ho(e.credential)||`—`,zr(e.cost_usd),Y(e.stop))).join(`
`):``;return D`<span class="num two">${t?D`<span>${W(t.input)} / ${W(t.output)}</span><span class="sub">${W(t.cache_read)} / ${W(t.cache_creation)}</span>`:D`<span class="jdim">—</span>`}</span>
      <span class="cost" title=${r||M(`Reported by the coding agent`)}>${zr(e.cost_usd)}</span>`}row(e,t,n,r){let i=K(e),a=i&&Ai(e),o=G(e),s=vo(e.hops),c=i?co((e.rounds??1)-1):``,l=M(o?`Python task`:`Agent task`);return D`<div class=${`jrow${a?` bad`:``}${i?``:` notrun`}${o?` py`:` agent`}${this.fresh.has(Mi(e))?` fresh`:``}`} style=${qc}
      @click=${()=>A(this,`ca-open-task`,o?{key:e.key,view:`output`}:{key:e.key})}>
      <span class="jmono" title=${Mr(e.ts,!0)}>${Mr(e.ts)}</span>
      <span class="jmono" title=${e.key}>${X(o,l,``)}
        ${U(e)}</span>
      ${An({text:D`<span class="nw">${this.shortStop(e.stop)}</span>${n&&i||c?D`<span class="sub">${H(n&&i?oo(e.attempt):``,c)}</span>`:O}`,tone:Oa(e.stop),cls:`two`,title:e.stop})}
      <span class="jmono jdim two" title=${H(e.route,s)||O}>${i?D`<span>${[e.agent,e.model].filter(Boolean).join(` / `)||`—`}</span>${this.identity(e)}`:`—`}</span>
      ${this.spend(e)}
      <span class="num">${i?D`${P(e.wall_s)}<span class="jdur"><i class=${a?`bad`:o?``:`llm`}
            style="width:${Math.max(2,Math.round(100*(e.wall_s||0)/t))}%"></i></span>`:`—`}</span>
      <span class="jwhy" title=${e.reason||O}>${this.reason(e,i,r)}${Br([e])?D` <span class="unread nw" title=${M(j`Event types from the coding agent that this contraagent version does not recognize: ${Br([e])}`)}
            ><span aria-hidden="true">⚠</span> ${M(`Unrecognized events`)}</span
          >`:O}</span>
    </div>`}};V([R({attribute:!1})],Jc.prototype,`rows`,void 0),V([R({attribute:!1})],Jc.prototype,`plan`,void 0),V([R({attribute:!1})],Jc.prototype,`fresh`,void 0),V([R()],Jc.prototype,`kind`,void 0),V([R()],Jc.prototype,`stop`,void 0),V([R()],Jc.prototype,`q`,void 0),V([R()],Jc.prototype,`run`,void 0),Jc=V([L(`ca-journal-table`),N()],Jc);var Yc=[`invalid`,`refused`,`failed`,`running`,`pending`,`valid`];function Xc(e){let t=e?.tally,n=t?Yc.filter(e=>t[e]):[];return n.length?n.map(e=>Pa(e,t?.[e])):D`<span class="meta">${M(`No checked files`)}</span>`}var Zc=e=>e.split(`/`).slice(-2).join(`/`),Qc=e=>U({kind:e.kind||e.key,unit:e.unit&&e.unit!==e.key?e.unit:``}),$c=e=>e?Yc.indexOf(e):Yc.length,el=class extends k{constructor(...e){super(...e),this.outputs=null,this.run=``,this.journal=[],this.plan=null,this.outcomes=new Map,this.open=new ni(`contracts:open`),this.producerOf=e=>{for(let t of this.outputs?.contracts??[]){let n=(t.outputs??[]).find(t=>t.path===e);if(n)return{name:Qc(t),written:!!n.file.exists,outcome:this.outcomes.get(t.key)?.outcome}}}}static{this.styles=[I,qa,es,w`
      :host { display: block; }
      .ct-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
      details.ct { border-top: 1px solid var(--line); }
      details.ct > summary { list-style: none; cursor: pointer; padding: 7px 4px; display: flex; align-items: center; gap: 10px; }
      details.ct > summary::-webkit-details-marker { display: none; }
      details.ct > summary::before { content: '▸'; color: var(--text-muted); width: 10px; transition: transform 0.15s; }
      details.ct[open] > summary::before { transform: rotate(90deg); }
      details.ct > summary:hover { background: var(--raise); border-radius: 8px; }
      .k-ic { margin-right: 0; }
      .ct-f { margin-left: auto; white-space: nowrap; }
      .ct-body { padding: 4px 10px 14px 24px; }
      .ct-links { margin-top: 10px; font-size: 12px; }
      .lead { margin: -4px 0 10px; }
      .one { display: flex; align-items: center; gap: 10px; padding: 7px 4px 7px 24px; border-top: 1px solid var(--line); flex-wrap: wrap; }
      .why { color: var(--text-2); font-size: 12px; }
    `]}render(){let e=this.outputs?.contracts??[];if(this.outcomes=this.plan?Zi(this.journal,this.plan).outcomes:new Map,!e.length)return D`<div class="blank"><span class="ic" aria-hidden="true">▣</span><b>${M(`No checked files`)}</b>
        <span>${M(`No task declares an OutputContract or an InputContract`)}</span></div>`;let t=e.flatMap(e=>(e.outputs??[]).map(t=>[e,t])).sort(([e,t],[n,r])=>$c(t.status)-$c(r.status)||e.key.localeCompare(n.key)),n=e.flatMap(e=>(e.inputs??[]).map(t=>[e,t]));return D`<div class="g12">
      <section class="panel c12">
        <h3 title=${M(`OutputContract`)}>${M(`Outputs`)}
          <span class="r">${M(`Files each task must write`)}</span></h3>
        <div class="ct-row">${Xc(this.outputs)}</div>
        ${B(t,([e,t])=>`out|${e.key}|${t.path}`,([e,t])=>this.outRow(e,t))}
      </section>
      ${n.length?D`<section class="panel c12">
            <h3 title=${M(`InputContract`)}>${M(`Inputs`)}
              <span class="r">${M(`Files each task reads, checked when the task starts`)}</span></h3>
            ${B(n,([e,t])=>`in|${e.key}|${t.path}`,([e,t])=>this.inRow(e,t))}
          </section>`:O}
    </div>`}details(e,t,n){return D`<details class="ct" ?open=${this.open.has(e)}
      @toggle=${t=>this.open.set(e,t.target.open)}>
      <summary class="ct-sum">${t}</summary>
      <div class="ct-body">${n}</div>
    </details>`}link(e,t,n){return D`<a class="lnk" href="#" @click=${n=>{n.preventDefault(),A(this,`ca-open-task`,{key:e,view:t})}}>${n}</a>`}who(e){let t=G(e);return D`${X(t,M(t?`Python task`:`Agent task`))}
      <b class="jmono" title=${e.key}>${Qc(e)}</b>`}reasonOf(e){for(let t=this.journal.length-1;t>=0;t--){let n=this.journal[t];if(n?.key===e)return q(n.reason,this.run)}return``}outRow(e,t){if(t.status===`refused`)return D`<div class="one">
        ${Pa(`refused`)}${this.who(e)}
        <span class="why">${Ca(t,this.run,this.producerOf)}</span>
      </div>`;let n=t.file,r=t.status,i=t.rounds??0,a=t.errors??[],o=Qc(e);return this.details(`out|${e.key}|${t.path}`,D`${Pa(r)}
        ${i>1?D`<span class="meta" title=${xa()}>${Sa(i,r===`valid`)}</span>`:O}
        ${this.who(e)}
        <span class="jmono jdim ct-path" title=${t.path}>${Zc(t.path)}</span>
        ${r===`failed`&&this.reasonOf(e.key)?D`<span class="why">${this.reasonOf(e.key)}</span>`:O}
        <span class="meta ct-f">${n.exists?`${n.size??0} B`:r?O:M(`No file`)}</span>`,D`${Ga(t,`output`)}
        ${Ba(t)}
        ${a.length?D`<h4>${M(`Errors`)}</h4><pre class="ct-err">${a.map(e=>q(e,this.run)).join(`
`)}</pre>`:O}
        <div class="ct-links">
          ${this.link(e.key,`output`,M(j`${o}: input and output`))}
          ${G(e)?O:D`<br />${this.link(e.key,`transcript`,M(j`${o}: transcript`))}`}
        </div>`)}inRow(e,t){let n=t.file,r=!!n.exists;return this.details(`in|${e.key}|${t.path}`,D`${Na(t)}
        ${this.who(e)}
        <span class="jmono jdim ct-path" title=${t.path}>${Zc(t.path)}</span>
        <span class="meta ct-f">${r?`${n.size??0} B`:M(`No file`)}</span>`,D`${Ga(t,`input`)}
        ${Ba(t)}
        <div class="ct-links">${this.link(e.key,`input`,M(j`${Qc(e)}: input`))}</div>`)}};V([R({attribute:!1})],el.prototype,`outputs`,void 0),V([R()],el.prototype,`run`,void 0),V([R({attribute:!1})],el.prototype,`journal`,void 0),V([R({attribute:!1})],el.prototype,`plan`,void 0),el=V([L(`ca-contracts`),N()],el);var tl=3e3,nl=class extends k{constructor(...e){super(...e),this.run=``,this.live=!1,this.journal=[],this.plan=null,this.selected=null,this.defs=[],this.defsRun=``,this.timer=null}static{this.styles=[I,w`
      :host { display: block; }
      .defs { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 14px; align-items: start; }
      .deflist { display: flex; flex-direction: column; gap: 6px; }
      .defitem { padding: 9px 12px; border-radius: 10px; background: var(--panel); border: 1px solid var(--line); cursor: pointer;
        display: flex; flex-direction: column; gap: 2px; }
      .defitem:hover { border-color: var(--line2); }
      .defitem.sel { border-color: var(--accent); background: var(--accent-bg); }
      @media (max-width: 900px) {
        .defs { grid-template-columns: 1fr; }
      }
    `]}disconnectedCallback(){super.disconnectedCallback(),this.clearTimer(),this.defsRun=``}connectedCallback(){super.connectedCallback(),this.run&&this.defsRun!==this.run&&this.load()}willUpdate(e){(e.has(`run`)||e.has(`client`))&&this.run&&this.client&&this.defsRun!==this.run&&(this.defs=[],this.load())}updated(){let e=new Set(this.tasks().filter(e=>!G(e)&&(e.tries.length||e.outcome===`running`)).map(e=>e.kind)).size;this.live&&this.defsRun===this.run&&this.defs.length<e&&!this.timer&&(this.timer=setTimeout(()=>{this.timer=null,this.load()},tl))}tasks(){return[...Zi(this.journal,this.plan).outcomes.values()]}clearTimer(){this.timer&&clearTimeout(this.timer),this.timer=null}async load(){if(!this.client||!this.run)return;let e=this.run;this.defsRun=e;let t=[];try{t=await this.client.definitions(e)}catch{t=[]}e===this.run&&(this.defs=t)}render(){let e=this.defs,t=this.tasks(),n=[...new Set(t.filter(e=>G(e)).map(e=>e.kind))].filter(t=>!e.some(e=>e.kind===t));if(!e.length&&!n.length)return D`<div class="blank"><span class="ic" aria-hidden="true">⌘</span><b>${this.live?M(`No definitions yet`):M(`No definitions`)}</b></div>`;let r=this.selected!==null&&n.includes(this.selected)?this.selected:null,i=r?void 0:e.find(e=>e.kind===this.selected)??e.find(e=>e.plugin)??e[0],a=r??i?.kind??n[0]??``,o=e=>{let n=t.filter(t=>t.kind===e),r=n.length,i=n.reduce((e,t)=>e+t.tries.length,0);return Fr(M(r===1?`1 task`:j`${r} tasks`),M(i===1?`1 attempt`:j`${i} attempts`))};return D`<div class="defs">
      <div class="deflist">
        ${B(e,e=>e.kind,e=>D`<div class="defitem ${e.kind===a?`sel`:``}" @click=${()=>A(this,`ca-navigate`,{def:e.kind})}>
            <b class="jmono">${e.kind}</b>
            <span class="meta words">${Vn([e.executor===`python`?`Python`:e.role?M(j`Role ${e.role}`):M(`No role`),...o(e.kind)])}</span>
          </div>`)}
        ${B(n,e=>e,e=>D`<div class="defitem ${e===a?`sel`:``}" @click=${()=>A(this,`ca-navigate`,{def:e})}>
            <b class="jmono">${e}</b>
            <span class="meta words">${Vn([`Python`,...o(e)])}</span>
          </div>`)}
      </div>
      <section class="panel">
        ${i?D`<h3 title=${M(`As recorded when its first task started (definitions/<kind>.json)`)}>
                ${i.kind}<span class="r">${i.executor===`python`?M(`Python task`):i.plugin?M(j`Plugin ${i.name||``}`):M(`Defined in Python code`)}</span>
              </h3>
              <ca-definition .definition=${i} memory="definition:${i.kind}"></ca-definition>`:D`<h3>${a}<span class="r">${M(`Python task`)}</span></h3>
              <ca-definition .definition=${null}></ca-definition>`}
      </section>
    </div>`}};V([R({attribute:!1})],nl.prototype,`client`,void 0),V([R()],nl.prototype,`run`,void 0),V([R({type:Boolean})],nl.prototype,`live`,void 0),V([R({attribute:!1})],nl.prototype,`journal`,void 0),V([R({attribute:!1})],nl.prototype,`plan`,void 0),V([R({attribute:!1})],nl.prototype,`selected`,void 0),V([z()],nl.prototype,`defs`,void 0),nl=V([L(`ca-definitions`),N()],nl);var rl=class extends k{constructor(...e){super(...e),this.procs=null}static{this.styles=[I,w`
      :host { display: block; }
      .cmd { word-break: break-all; }
    `]}render(){let e=this.procs;if(!e?.alive)return D`<div class="blank"><span class="ic" aria-hidden="true">⚙</span><b>${H(M(`No processes`),M(`run not running`))}</b></div>`;let t=e.python_tasks;return D`<div class="g12">
      <section class="panel c12">
        <h3 title=${M(`One per task (Backend.run)`)}>${M(`Agent sessions running`)} <span class="r">${e.launches.length}</span></h3>
        ${e.launches.length?B(e.launches,e=>e.key,e=>D`<div class="fl" @click=${()=>A(this,`ca-open-task`,{key:e.key})}>
                <b class="jmono">${U(e)}</b>
                <span class="meta">${H(M(j`PID ${e.pid}`),M(j`Model ${e.model||`—`}`),e.role?M(j`Role ${e.role}`):``)} |
                  <cae-elapsed .since=${hn.at(`c:${e.key}`,e.age_s)}></cae-elapsed></span>
                <div class="meta mono cmd">${(e.full_cmd||M(`In the pipeline process`)).slice(0,400)}</div>
              </div>`):D`<div class="meta">${M(`No agent sessions`)}</div>`}
      </section>
      ${t.length?D`<section class="panel c12">
            <h3 title=${M(`Functions in the pipeline process`)}>${M(`Python tasks running`)} <span class="r">${t.length}</span></h3>
            ${B(t,e=>e.key,e=>D`<div class="fl">
                <b class="jmono">${U(e)}</b>
                <span class="meta">${M(j`PID ${e.pid}`)} | <cae-elapsed .since=${hn.at(`p:${e.key}`,e.age_s)}></cae-elapsed></span>
              </div>`)}
          </section>`:O}
      <section class="panel c12"><h3>${M(`Process tree`)}</h3><ca-proc-tree .procs=${e}></ca-proc-tree></section>
    </div>`}};V([R({attribute:!1})],rl.prototype,`procs`,void 0),rl=V([L(`ca-procs-view`),N()],rl);var il=class extends k{constructor(...e){super(...e),this.name=``}static{this.styles=[I,w`
      :host { display: block; }
      .tab-ic { opacity: 1; margin-right: 6px; font-size: 12px; }
      .desc { margin: -4px 0 12px; }
    `]}render(){if(this.data===void 0)return this.panel?D`<div class="blank"><span class="ic" aria-hidden="true">…</span>${M(`Loading…`)}</div>`:D`<div class="blank"><span class="ic" aria-hidden="true">▤</span>${M(j`No custom view named ${this.name}`)}</div>`;let e=this.panel;return D`<section class="panel">
      <h3><span class="tab-ic" aria-hidden="true">${e?.icon||`▤`}</span>${e?.title||this.name}
        <span class="r">${M(`Custom view`)}</span></h3>
      ${e?.description?D`<div class="meta desc">${e.description}</div>`:O}
      <cae-json-tree .value=${this.data}></cae-json-tree>
    </section>`}};V([R()],il.prototype,`name`,void 0),V([R({attribute:!1})],il.prototype,`panel`,void 0),V([R({attribute:!1})],il.prototype,`data`,void 0),il=V([L(`ca-panel-view`),N()],il);var al=e=>({key:e,rows:[],launches:[],definition:null,io:{params:{},inputs:[],outputs:[],executor:`agent`,upstream:[],downstream:[]},stream:null}),ol=class{constructor(e){this.host=e,this.value=null,this.error=null,this.token=0}load(e,t,n){let r=++this.token;this.value=null,this.error=null,t&&n&&e&&this.fetch(r,e,t,n)}async fetch(e,t,n,r){let i,a=null;try{i=await t.task(n,r)}catch(e){i=al(r),a=e}e===this.token&&(this.value=i,this.error=a,this.host.requestUpdate())}};un(`cae-markdown`,Er);function sl(e){return D`<cae-markdown .text=${e} .split=${Ur} .strings=${{showRendered:M(`Show rendered`),showSource:M(`Show source`)}}></cae-markdown>`}function cl(e,t,n=oo(e.tryNo-1)){return t>1?e.fixupNo?H(n,M(j`correction ${e.fixupNo}`)):e.hopNo?H(n,M(`model switch`)):n:e.fixupNo?M(j`Correction ${e.fixupNo}`):e.hopNo?M(`Model switch`):oo(0)}function ll(e,t=!1){return e.fixupNo?M(`same agent session, after failed checks`):e.hopNo?M(`new agent session on the next model`):e.tryNo>1&&t?M(`new agent session in the resumed run`):e.tryNo>1?M(j`new agent session after attempt ${e.tryNo-1} failed`):M(`first agent session`)}function ul(e){let t=e.model||M(`model`);return e.switchedTo?M(j`${t}: ${Y(e.switchedStop)}; switched to ${e.switchedTo}`):M(j`${t}: ${Y(e.switchedStop)}; switched to the next model`)}function dl(e,t){switch(e.result){case`ok`:return[`✓`,M(`passed`),M(`Output passed checks`)];case`rejected`:return[`✕`,M(`failed checks`),M(`Output failed checks`)];case`switched`:return[`✕`,Y(e.switchedStop),ul(e)];case`failed`:return[`✕`,M(`failed`),q(e.row?.reason,t)||Y(e.row?.stop)];default:return[``,``,``]}}var fl={claude:`Claude Code`,omp:`omp`,codex:`Codex`,opencode:`opencode`,gemini:`Gemini CLI`};function pl(e){let t=String(e||``).split(`/`).pop()??``;return fl[t]??t}var ml=(e,t)=>{let n=e.indexOf(t);return n>=0?e[n+1]??``:``};function hl(e){let t=e.argv,n=/TELEMETRY [^\n]*role=([\w:-]+)/.exec(e.prompt||``)?.[1];return{agent:pl(t[0]),model:ml(t,`--model`)||ml(t,`-m`),role:n&&n!==`-`?n:``}}var gl=()=>({rounds:[],tools:new Map,next:0}),_l=/session init:.*?model=([\w.\-:]+)/;function vl(e){return`i${e.next++}`}function yl(e,t){let n={id:`r${e.rounds.length}`,launch:t,who:t?hl(t):null,items:[]};return e.rounds.push(n),n}function bl(e){return e.rounds[e.rounds.length-1]??yl(e,null)}function xl(e,t){t?e.name=t:e.name||=`tool`,e.icon=(e.name.split(/[_:]/).pop()??``).toLowerCase()}function Sl(e,t,n){let r=n?e.tools.get(n):void 0;return r||(r={kind:`tool`,id:n?`call:${n}`:vl(e),call:n,name:``,icon:``,preview:``,intent:``,cmd:``,webQuery:``,webFetch:``,out:null,status:`run`},n&&e.tools.set(n,r),t.items.push(r)),r}function Cl(e,t){let n=0;for(let r of t){let t=ai(r);if(!t)continue;if(t.type===`launch`){yl(e,t),n++;continue}let i=bl(e);switch(t.type){case`message_start`:case`message_end`:if(t.role!==`user`||!t.text)continue;i.items.push({kind:`prompt`,id:vl(e),text:t.text});break;case`turn_end`:if(!t.thinking)continue;i.items.push({kind:`summary`,id:vl(e),text:t.thinking});break;case`acall`:case`tool_execution_start`:case`tool_execution_update`:{let n=Sl(e,i,t.call);n.out===null?(xl(n,t.tool),n.preview=Rr(t.cmd),n.intent=t.intent||``,n.cmd=t.cmd||n.cmd,t.web_query&&(n.webQuery=t.web_query),t.web_fetch&&(n.webFetch=t.web_fetch)):!n.preview&&t.cmd&&(n.preview=Rr(t.cmd));break}case`aresult`:case`tool_execution_end`:{let n=Sl(e,i,t.call);if(n.out!==null&&!t.out)break;xl(n,t.tool),n.status=t.err?`err`:`ok`,!n.preview&&n.cmd&&(n.preview=Rr(n.cmd)),n.out=t.out||`(no output)`;break}case`message_update`:{if(!t.delta)continue;let n=i.items[i.items.length-1];n?.kind===`assistant`?n.raw+=t.delta:i.items.push({kind:`assistant`,id:vl(e),raw:t.delta});break}case`auto_retry_start`:i.items.push({kind:`retry`,id:vl(e),err:t.err??``});break;case`notice`:{let n=_l.exec(t.text||``)?.[1];n&&(i.who??={agent:``,model:``,role:``},i.who.model||(i.who.model=n)),i.items.push({kind:`notice`,id:vl(e),text:(t.text||``).replace(/\s+/g,` `).trim()});break}}n++}return n}var wl=`The output file(s) you wrote do not pass their checks.`;function Tl(e){let t=[],n=!1;for(let r of(e||``).split(`
`))/^Errors:\s*$/.test(r)?n=!0:n&&r.startsWith(`- `)?t.push(r.slice(2)):n&&r.trim()&&!r.startsWith(`- `)&&(n=!1);return t}var El=e=>!!e&&(e.prompt||``).startsWith(wl);function Dl(e,t){let n=new Map(t.filter(e=>e.stop!==`invalid_input`&&e.stop!==`skipped`).map((e,t)=>[t+1,e])),r=[],i=0,a=0,o=0;return e.forEach((e,t)=>{let s=n.get(i)?.hops?.length??1;t>0&&El(e)?a++:t>0&&o+1<s?(o++,a=0):(i++,o=0,a=0);let c=n.get(i)?.hops?.[o],l=c?.model||c?.route||``,u=a?`fixup`:o?`switch`:`try`;r.push({kind:u,tryNo:i,fixupNo:a,hopNo:o,model:l,result:null,rejectedWith:[],switchedStop:``,switchedTo:``,row:null})}),r.forEach((t,i)=>{let a=r[i+1];if(a&&a.tryNo===t.tryNo&&a.hopNo!==t.hopNo){t.result=`switched`,t.switchedStop=n.get(t.tryNo)?.hops?.[t.hopNo]?.stop??``,t.switchedTo=a.model;return}if(a&&a.tryNo===t.tryNo){t.result=`rejected`,t.rejectedWith=Tl(e[i+1]?.prompt);return}let o=n.get(t.tryNo)??null;t.row=o,t.result=o?o.ok?`ok`:`failed`:null}),r}function Ol(e){let t=/\[([\w.-]+)\]\s*(.*)$/.exec(e);return t?`${t[1]}: ${t[2]}`:e}var kl=20,Al=/\{\s*"title"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"url"\s*:\s*"(https?:\/\/[^"\s]+)"/g,jl=/^\s*\[\d+\]\s+(.+)\n\s*(https?:\/\/\S+)/gm,Ml=/https?:\/\/[^\s"'<>)\]]+/g;function Nl(e){let t=e??``,n=[],r=new Set,i=(e,t)=>{r.has(t)||n.length>=kl||(r.add(t),n.push({title:e.trim()||t,url:t}))};for(let e of t.matchAll(Al)){let t=e[1]??``;try{t=JSON.parse(`"${t}"`)}catch{}i(t,e[2]??``)}if(!n.length)for(let e of t.matchAll(jl))i(e[1]??``,e[2]??``);if(!n.length)for(let e of t.matchAll(Ml))i(``,e[0].replace(/[.,;:!?]+$/,``));return n}function Pl(e){return e?D`${e.agent?D`<span class="who agent" title=${M(`The CLI that ran the task (claude, omp)`)}
        ><span class="who-l">${M(`coding agent`)}</span>${e.agent}</span
      >`:O}${e.model?D`<span class="who model" title=${M(`The language model the coding agent used`)}
        ><span class="who-l">${M(`model`)}</span>${e.model}</span
      >`:O}${e.role?D`<span class="who role" title=${M(`The agent definition the coding agent ran as (agents/<role>.md)`)}
        ><span class="who-l">${M(`role`)}</span>${e.role}</span
      >`:O}`:D``}var Fl=w`
  .who { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; font-weight: 600; padding: 2px 9px;
    border-radius: 7px; border: 1px solid var(--line2); white-space: nowrap; }
  /* facts, not statuses: neutral chips, the label muted and the value in the text colour */
  .who-l { font-size: 10px; font-weight: 400; color: var(--text-muted); font-family: var(--sans); }
  .who.agent, .who.model { color: var(--text); background: var(--raise); }
  .who.model { font-family: var(--mono); }
  .who.role { color: var(--text-2); font-family: var(--mono); font-weight: 500; }
`,Il=60,Ll=1200,Rl=4e3,zl=3e3,Bl=4e3;function Vl(e){try{return new URL(e).host}catch{return``}}var $=class extends k{constructor(...e){super(...e),this.events=null,this.run=``,this.stream=null,this.baseUrl=``,this.client=null,this.live=!1,this.round=null,this.rows=[],this.mode=`full`,this.version=0,this.behind=0,this.bulk=!0,this.unseen=0,this.pinned=null,this.revealed=``,this.revealPending=!1,this.model=gl(),this.close=null,this.loaded=``,this.token=0,this.first=!0,this.stick=!0,this.restored=!1,this.lastTop=0,this.lastShown=-1,this.lastSent=``,this.openCards=new ri(`transcript::open`),this.folds=new Set,this.openPrompts=new Set,this.mdCache=new WeakMap}static{this.styles=[I,wn,Fl,w`
      :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
      :host([mode='none']) { display: none; }
      :host([mode='tabs']) { flex: none; }
      :host([mode='tabs']) .scroller, :host([mode='tabs']) .newpill { display: none; }

      .rounds { flex: none; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 0 0 10px; padding-left: 2px; }
      .rounds-lbl { color: var(--text-muted); font-size: 11.5px; font-weight: 600; margin-right: 4px; cursor: help; }
      .stab { padding: 3px 11px; border: 1px solid var(--line); border-radius: 999px; background: var(--card); color: var(--text-muted);
        cursor: pointer; font-size: 12px; display: inline-flex; align-items: center; }
      .stab:hover { border-color: var(--accent); }
      .stab.sel { background: var(--accent-bg); border-color: var(--accent); color: var(--text); }
      .stab-m { font-family: var(--mono); font-size: 10.5px; color: var(--text-muted); margin-left: 4px; }
      .stab .dot { width: 6px; height: 6px; margin-left: 4px; }
      .stab .mk { margin-right: 4px; }
      .stab .mk.ok { color: var(--status-done); }
      .stab .mk.bad { color: var(--status-failed); }
      .verdict { margin: 6px 10px 4px 41px; padding: 7px 11px; border-radius: 10px; border: 1px solid; font-size: 12px; }
      .verdict[data-tone] { background: var(--tone-bg); color: var(--text); }
      .verdict[data-tone='attention'] { border-color: color-mix(in srgb, var(--tone) 40%, transparent); }
      .verdict[data-tone='failed'] { border-color: color-mix(in srgb, var(--tone) 45%, transparent); }
      .verdict b { display: block; margin-bottom: 2px; }
      .verdict ul { margin: 2px 0 0; padding-left: 18px; font-family: var(--mono); font-size: 11.5px; }

      .scroller { flex: 1 1 auto; min-height: 0; overflow: auto; border: 1px solid var(--line); border-radius: 14px;
        background: linear-gradient(180deg, var(--panel), var(--well)); padding: 4px 2px 8px; font-size: 12.5px; }
      .back { margin: 6px 10px; background: var(--raise); border: 1px solid var(--line2); border-radius: 8px; padding: 3px 10px; cursor: pointer; color: var(--text-2); }
      .back:hover { border-color: var(--accent); }

      .inv-body { display: flex; flex-direction: column; gap: 10px; }
      .inv-head { border: 1px solid var(--line2); border-radius: 12px; background: var(--raise); padding: 8px 10px; margin: 4px 8px 6px; }
      .inv-who { display: flex; flex-wrap: wrap; gap: 6px; }
      .inv-cmdbox { margin-top: 6px; }
      .inv-cmdbox summary, .inv-prompt summary { cursor: pointer; font-size: 11px; color: var(--text-muted); }
      .inv-prompt summary { font-size: 11.5px; }
      .inv-prompt summary:hover { color: var(--accent); }
      .inv-cmd { font-family: var(--mono); font-size: 11.5px; white-space: pre-wrap; word-break: break-all; margin: 4px 0 6px; max-height: 160px; overflow: auto; color: var(--text); }
      .inv-ptext { margin-top: 6px; max-height: 360px; overflow: auto; }

      .msg { display: flex; gap: 9px; padding: 3px 10px; }
      .av { width: 22px; height: 22px; flex: 0 0 22px; border-radius: 7px; line-height: 22px; font-size: 11px; text-align: center; font-weight: 700; }
      .av-a { background: var(--agent-bg); color: var(--agent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--agent) 35%, transparent); }
      .av-l { background: var(--raise); color: var(--text-2); }
      .av-t { background: var(--raise); color: var(--text-muted); }
      .bd { flex: 1; min-width: 0; background: color-mix(in srgb, var(--text) 2.5%, transparent); border: 1px solid var(--line); border-radius: 3px 10px 10px 10px; padding: 5px 10px; }
      .hd { font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 1px; }
      .tx { color: var(--text); line-height: 1.5; word-break: break-word; }
      .tx pre, .tx code { white-space: pre-wrap; }
      .tx pre { margin: 0 0 4px; }

      .toolcard, .typing { margin-left: 41px; margin-right: 10px; }
      .toolcard { border: 1px solid var(--line); border-left: 3px solid var(--line2); border-radius: 10px; margin-top: 3px; margin-bottom: 3px;
        overflow: hidden; background: var(--well); transition: border-color 0.3s; }
      .toolcard.run { border-left-color: var(--status-running); }
      .toolcard.err { border-left-color: var(--status-failed); }
      .th { display: flex; gap: 9px; align-items: baseline; padding: 4px 9px; cursor: pointer; }
      .th:hover { background: color-mix(in srgb, var(--text) 4%, transparent); }
      .tn { font-family: var(--mono); font-weight: 600; flex: none; display: inline-flex; align-items: center; }
      .tn::before { content: '⚒'; display: inline-grid; place-items: center; width: 20px; height: 20px; margin-right: 7px;
        border-radius: 6px; background: var(--raise); color: var(--text-2); font-size: 11px; }
      /* a tool's icon: its shape tells the tool; the colour stays neutral (a colour is a status) */
      .toolcard[data-tool='bash'] .tn::before { content: '❯'; }
      .toolcard[data-tool='read'] .tn::before { content: '▤'; }
      .toolcard[data-tool='grep'] .tn::before, .toolcard[data-tool='glob'] .tn::before { content: '⌕'; }
      .toolcard[data-tool='edit'] .tn::before, .toolcard[data-tool='write'] .tn::before { content: '✎'; }
      .toolcard[data-tool='task'] .tn::before, .toolcard[data-tool='agent'] .tn::before { content: '✦'; color: var(--agent); }
      .toolcard[data-tool='web-search'] .tn::before { content: '◍'; }
      .toolcard[data-tool='web-fetch'] .tn::before { content: '⇣'; }
      .toolcard.revealed { box-shadow: 0 0 0 1px var(--accent); }
      .tp { font-family: var(--mono); font-size: 11.5px; color: var(--text); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .ti { color: var(--text-muted); font-size: 11px; flex: none; max-width: 35%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .st-run, .st-ok, .st-err, .st-int { flex: none; white-space: nowrap; }
      .st-run { color: var(--status-running); display: inline-flex; align-items: center; gap: 6px; }
      .st-ok { color: var(--text-muted); }
      .st-ok > [aria-hidden] { color: var(--status-done); font-weight: 700; }
      .st-err { color: var(--status-failed); }
      .st-int { color: var(--status-attention); }
      .pdot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--status-running); animation: breathe 1.8s ease-in-out infinite; }
      .tb { padding: 6px 9px; border-top: 1px solid var(--line); background: var(--bg); }
      .tb pre { white-space: pre-wrap; word-break: break-word; margin: 4px 0; font-family: var(--mono); font-size: 12px; }
      .fold { max-height: 220px; overflow: hidden; position: relative; }
      .fold.open { max-height: none; }
      .foldbtn { cursor: pointer; color: var(--accent); font-size: 11px; background: none; border: 0; padding: 0; font-family: inherit; }
      .wq { font-size: 12px; margin: 2px 0 6px; }
      .wq b { font-family: var(--mono); font-weight: 600; }
      .wl { color: var(--text-muted); font-size: 11px; margin-right: 6px; }
      .links { margin: 0 0 6px; padding-left: 30px; font-size: 12px; }
      .links li { margin: 2px 0; overflow-wrap: anywhere; }
      .links a { color: var(--accent); text-decoration: none; }
      .links a:hover { text-decoration: underline; }
      .rawfold > summary { cursor: pointer; color: var(--text-muted); font-size: 11px; }
      .plink { color: var(--accent); text-decoration: none; font-family: var(--mono); overflow-wrap: anywhere; }
      .plink:hover { text-decoration: underline; }
      .host { color: var(--text-muted); font-family: var(--mono); font-size: 11px; margin-left: 6px; }

      .sysline { display: flex; gap: 8px; align-items: baseline; padding: 2px 10px 2px 41px; font-size: 11px; color: var(--text-muted); font-family: var(--mono); }
      .sysline .tx { color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .typing { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
      .typing .av { width: 26px; height: 26px; flex: 0 0 26px; border-radius: 9px; display: grid; place-items: center; font-size: 12px; }
      .dots { display: inline-flex; gap: 4px; padding: 8px 12px; border-radius: 12px; background: var(--agent-bg); }
      .dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--agent); animation: bounce 1.2s infinite ease-in-out; }
      .dots i:nth-child(2) { animation-delay: 0.15s; }
      .dots i:nth-child(3) { animation-delay: 0.3s; }
      .scroller:not(.bulk) .msg, .scroller:not(.bulk) .toolcard { animation: enter 0.35s var(--ease) both; }

      .newpill { position: absolute; left: 50%; bottom: 26px; transform: translateX(-50%); z-index: 5; cursor: pointer; padding: 6px 14px;
        border-radius: 999px; border: 1px solid var(--accent); background: color-mix(in srgb, var(--panel) 92%, transparent); color: var(--accent);
        font-size: 12px; font-weight: 600; box-shadow: 0 10px 28px color-mix(in srgb, var(--shadow) 50%, transparent); backdrop-filter: blur(6px); animation: toast-in 0.3s var(--ease) both; }
      .newpill:hover { background: var(--accent-bg); }
    `]}get source(){return this.events?`static`:this.run&&this.stream?`${this.run}\n${this.stream}`:``}get memoryId(){return`transcript:${this.run}/${this.stream??``}`}disconnectedCallback(){super.disconnectedCallback(),this.close?.(),this.close=null,this.loaded=``}connectedCallback(){super.connectedCallback(),this.hasUpdated&&this.requestUpdate()}willUpdate(e){let t=this.source;(e.has(`events`)||t!==this.loaded)&&this.load(t)}load(e){if(this.close?.(),this.close=null,this.loaded=e,this.token++,this.model=gl(),this.first=!0,this.behind=0,this.bulk=!0,this.unseen=0,this.pinned=null,this.stick=!0,this.restored=!1,this.lastShown=-1,this.folds.clear(),this.openPrompts.clear(),this.openCards=new ri(`${this.memoryId}:open`),this.events){Cl(this.model,this.events),this.version++,this.afterFirstPage(this.token);return}if(!e||!this.stream)return;let t=this.token;this.close=Ei(this.run,this.stream,{message:e=>this.onPage(e,t)},{baseUrl:this.baseUrl})}onPage(e,t){if(t!==this.token)return;this.first&&e.behind&&(this.behind=e.behind);let n=this.model.rounds.length,r=Cl(this.model,e.events);if(n&&this.model.rounds.length>n&&this.round===null&&this.pinned===null&&!this.stick&&!this.bulk&&(this.pinned=n),this.version++,this.first){this.first=!1,this.afterFirstPage(t);return}this.updateComplete.then(()=>{t===this.token&&(this.stick&&this.onLiveRound()?this.toBottom():this.unseen+=r)})}async afterFirstPage(e){if(await this.updateComplete,e!==this.token)return;let t=this.stream?$r(`${this.memoryId}:scroll`):void 0,n=this.scroller;if(!t||t.stick||!n)this.stick=!0,this.toBottom();else{this.stick=!1;let r=performance.now()+Bl;await new Promise(i=>{let a=()=>{let o=n.scrollHeight-n.clientHeight;n.scrollTop=Math.min(t.top,o),o>=t.top||performance.now()>r||e!==this.token?i():requestAnimationFrame(a)};a()}),this.lastTop=n.scrollTop}this.restored=!0,requestAnimationFrame(()=>{e===this.token&&(this.bulk=!1)})}shownIndex(){let e=this.model.rounds.length;if(!e)return-1;let t=this.round===null?this.pinned??e-1:this.round-1;return Math.max(0,Math.min(e-1,t))}onLiveRound(){let e=this.model.rounds.length;return e<2||this.shownIndex()===e-1}toBottom(e=!1){let t=this.scroller;t&&(e?t.scrollTo({top:t.scrollHeight,behavior:`smooth`}):t.scrollTop=t.scrollHeight)}onScroll(){let e=this.scroller;e&&e.clientHeight&&(this.stick=e.scrollHeight-e.scrollTop-e.clientHeight<Il,this.lastTop=e.scrollTop,this.stick&&this.onLiveRound()&&(this.unseen=0),this.restored&&this.stream&&ei(`${this.memoryId}:scroll`,{stick:this.stick,top:Math.round(e.scrollTop)}))}updated(e){let t=this.shownIndex();if(t!==this.lastShown){let e=this.lastShown;this.lastShown=t,e!==-1&&this.restored&&this.toBottom()}let n=e.get(`mode`);n&&n!==`full`&&this.mode===`full`&&this.scroller&&(this.stick?this.toBottom():this.scroller.scrollTop=this.lastTop);let r=`${this.version}|${t}|${this.model.rounds.length}|${this.rows.length}`;if(r!==this.lastSent){this.lastSent=r;let e={launches:this.model.rounds.map(e=>e.launch),shown:t,rounds:this.infos()};A(this,`ca-rounds`,e,{bubbles:!1})}if(this.revealPending){let e=this.renderRoot.querySelector(`[data-card="${CSS.escape(this.revealed)}"]`);e&&this.mode===`full`&&(this.revealPending=!1,this.stick=!1,e.scrollIntoView({block:`center`}))}}infos(){return Dl(this.model.rounds.map(e=>e.launch),this.rows)}pickRound(e){this.pinned=null;let t=this.model.rounds.length-1;A(this,`ca-navigate`,{round:e===t?null:e+1})}jumpToLive(){let e=this.model.rounds.length;e>1&&this.shownIndex()!==e-1&&(this.pinned=null,this.round!==null&&A(this,`ca-navigate`,{round:null})),this.stick=!0,this.unseen=0,this.updateComplete.then(()=>this.toBottom(!0))}async loadEarlier(){let{run:e,stream:t}=this;if(!t)return;let n=this.token,r=Math.max(0,this.behind-zl);this.behind=0;let i=await(this.client??xi({baseUrl:this.baseUrl})).stream(e,t,r);n===this.token&&(this.model=gl(),this.lastShown=-1,Cl(this.model,i.events),this.version++)}render(){let e=this.model.rounds,t=this.shownIndex(),n=e[t],r=this.onLiveRound();return D`${this.renderRounds(e,t)}
      <div class="scroller ${this.bulk?`bulk`:``}" @scroll=${()=>this.onScroll()}>
        ${this.behind?D`<div class="meta"><button type="button" class="back" @click=${()=>void this.loadEarlier()}>
              ${this.behind===1?M(`Show 1 earlier line`):M(j`Show ${this.behind} earlier lines`)}</button></div>`:O}
        ${n?this.renderRound(n,t===e.length-1,this.infos()[t]):O}
        ${!n&&this.live?this.typing():O}
      </div>
      ${this.unseen?D`<button type="button" class="newpill" @click=${()=>this.jumpToLive()}>
            ${this.unseen===1?M(r?`Show 1 new event`:`Show 1 new event in the running agent session`):M(r?j`Show ${this.unseen} new events`:j`Show ${this.unseen} new events in the running agent session`)}</button>`:O}`}renderRounds(e,t){if(e.length<2)return O;let n=e.length-1,r=this.infos(),i=r[r.length-1]?.tryNo??1,a=so(this.rows.filter(K));return D`<div class="rounds" role="group" aria-label=${M(`Agent sessions`)}>
      <span class="rounds-lbl"
        title=${[M(`Attempt: a new agent session`),M(`Correction: the same agent session after failed checks`),M(`Model switch: a new agent session on the next model`)].join(`
`)}
        >${M(`Agent sessions`)}</span>
      ${e.map((e,o)=>{let s=r[o],[c,l,u]=s?dl(s,this.run):[``,``,``];return D`<button type="button" class="stab ${o===t?`sel`:``}" title=${u||O} aria-pressed=${o===t}
          @click=${()=>this.pickRound(o)}>
          ${c?D`<span class="mk ${c===`✓`?`ok`:`bad`}" aria-hidden="true">${c}</span><span class="sr">${l}</span>`:O}${s?cl(s,i,a[s.tryNo-1]):String(o+1)}
          ${e.who?.model?D` <span class="stab-m">${e.who.model.replace(/^claude-/,``)}</span>`:O}
          ${o===n&&this.live&&this.close?D`<span class="dot" data-tone="running"></span>`:O}
        </button>`})}
    </div>`}renderRound(e,t,n){return D`<div class="inv-body">
      ${e.launch?this.renderHead(e,e.launch):O}
      ${B(e.items,e=>e.id,e=>this.renderItem(e))}
      ${t&&this.live?this.typing():O}
      ${n?this.renderVerdict(n):O}
    </div>`}renderVerdict(e){if(e.result===`rejected`)return D`<div class="verdict" data-tone="attention">
        <b>${M(`Output failed checks`)}</b>
        ${e.rejectedWith.length?D`<ul>${e.rejectedWith.map(e=>D`<li>${q(e,this.run)}</li>`)}</ul>`:D`<span class="meta">${M(`The errors are in the correction prompt`)}</span>`}
      </div>`;if(e.result===`switched`)return D`<div class="verdict" data-tone="failed">
        <b>${ul(e)}</b>
      </div>`;if(e.result===`failed`&&e.row){let t=q(e.row.reason,this.run)||Y(e.row.stop);return D`<div class="verdict" data-tone="failed"><b>${M(j`Attempt ${e.tryNo} failed: ${t}`)}</b></div>`}return O}renderHead(e,t){let n=t.prompt||``,r=t.prompt_truncated||0,i=this.openPrompts.has(e.id);return D`<div class="inv-head">
      <div class="inv-who">${Pl(e.who)}</div>
      <details class="inv-cmdbox"><summary>${M(`Command line`)}</summary><pre class="inv-cmd"><code>${t.argv.join(` `)}</code></pre></details>
      <details class="inv-prompt" ?open=${i}
        @toggle=${t=>{let n=t.target.open;n!==this.openPrompts.has(e.id)&&(n?this.openPrompts.add(e.id):this.openPrompts.delete(e.id),this.requestUpdate())}}>
        <summary>${M(r?j`Prompt (${n.length} characters; ${r} characters not saved)`:j`Prompt (${n.length} characters)`)}</summary>
        ${i?D`<div class="inv-ptext">${sl(n+(r?`\n\n${M(j`(${r} characters not saved)`)}`:``))}</div>`:O}
      </details>
    </div>`}mdOf(e,t){let n=this.mdCache.get(e);if(n?.raw===t)return n.html;let r=xr(t);return this.mdCache.set(e,{raw:t,html:r}),r}bubble(e,t,n,r,i){return D`<div class="msg" title=${i??O}>
      <div class="av ${t}">${e}</div>
      <div class="bd"><div class="hd">${n}</div>${r}</div>
    </div>`}renderItem(e){switch(e.kind){case`prompt`:return this.bubble(`▸`,`av-l`,M(`Prompt`),D`<div class="tx meta">${M(j`${e.text.length} characters`)}</div>`,e.text.slice(0,600));case`assistant`:return this.bubble(`A`,`av-a`,M(`Assistant`),D`<div class="tx">${wr(this.mdOf(e,e.raw))}</div>`);case`summary`:return this.bubble(`✦`,`av-t`,M(`Reasoning`),D`<div class="tx">${wr(this.mdOf(e,e.text))}</div>`);case`retry`:return D`<div class="msg"><div class="av av-t" aria-hidden="true">↻</div><div class="bd"><div class="hd">${M(`API request sent again`)}</div>${e.err?D`<div class="tx meta">${e.err}</div>`:O}</div></div>`;case`notice`:return D`<div class="sysline"><span aria-hidden="true">⚙</span><span class="tx">${e.text}</span></div>`;case`tool`:return this.toolCard(e)}}toolCard(e){let t=this.openCards.has(e.id),n=e.webQuery?Nl(e.out):[],r=e.status===`ok`?D`<span class="st-ok"><span aria-hidden="true">✓</span> ${M(`done`,{id:`tool-done`,desc:`A tool call that finished`})}</span>`:e.status===`err`?D`<span class="st-err"><span aria-hidden="true">✕</span> ${M(`failed`)}</span>`:this.live?D`<span class="st-run"><i class="pdot"></i>${M(`running`)}</span>`:D`<span class="st-int" title=${M(`The run ended before the tool call returned`)}><span aria-hidden="true">◌</span> ${M(`interrupted`)}</span>`,i=e.webQuery?`web-search`:e.webFetch?`web-fetch`:e.icon;return D`<div class="toolcard ${e.status} ${this.revealed===e.id?`revealed`:``}" data-tool=${i} data-card=${e.id}>
      <div class="th" @click=${()=>{this.openCards.set(e.id,!t),this.requestUpdate()}}>
        <span class="tn">${e.name||M(`tool`)}</span><span class="tp">${e.preview}</span><span class="ti"
          >${n.length===1?M(`1 result`):n.length?M(j`${n.length} results`):e.intent}</span
        >${r}
      </div>
      ${t?D`<div class="tb">${e.webQuery?this.webSearchBody(e,n):e.webFetch?this.webFetchBody(e):this.toolBody(e)}</div>`:O}
    </div>`}toolBody(e){return e.out===null?this.codeBlock(e.cmd,`${e.id}:cmd`):D`${e.cmd?this.codeBlock(e.cmd,`${e.id}:cmd`):O}${this.codeBlock(e.out,`${e.id}:out`)}`}webSearchBody(e,t){return D`<div class="wq"><span class="wl">${M(`query`)}</span><b>${e.webQuery}</b></div>
      ${t.length?D`<ol class="links">
            ${t.map(e=>D`<li><a href=${e.url} target="_blank" rel="noopener noreferrer">${e.title}</a><span class="host">${Vl(e.url)}</span></li>`)}
          </ol>`:O}
      ${e.out===null?O:t.length?D`<details class="rawfold"><summary>${M(`Full text`)}</summary>${this.codeBlock(e.out,`${e.id}:out`)}</details>`:this.codeBlock(e.out,`${e.id}:out`)}`}webFetchBody(e){let t=/^https?:\/\//.test(e.webFetch)?e.webFetch:``;return D`<div class="wq">
        <span class="wl">${M(`page`)}</span>${t?D`<a class="plink" href=${t} target="_blank" rel="noopener noreferrer">${t}</a>`:D`<b>${e.webFetch}</b>`}
      </div>
      ${e.out===null?O:this.codeBlock(e.out,`${e.id}:out`)}`}revealWebSearch(e,t=0){let n=0,r=this.model.rounds.length-1;for(let[i,a]of this.model.rounds.entries())for(let o of a.items)if(o.kind===`tool`&&o.webQuery===e&&n++===t)return this.openCards.set(o.id,!0),this.pinned=null,this.revealed=o.id,this.revealPending=!0,this.requestUpdate(),{round:i===r?null:i+1}}codeBlock(e,t){let n=D`<pre><code>${e.slice(0,Rl)}</code></pre>`;if(e.length<=Ll)return n;let r=this.folds.has(t);return D`<div>
      <div class="fold ${r?`open`:``}">${n}</div>
      <button type="button" class="foldbtn" @click=${()=>{r?this.folds.delete(t):this.folds.add(t),this.requestUpdate()}}>${M(r?`Show less`:j`Show all (${e.length} characters)`)}</button>
    </div>`}typing(){return D`<div class="typing"><span class="av av-a">A</span><span class="dots"><i></i><i></i><i></i></span><span class="meta">${M(`running`)}</span></div>`}};V([R({attribute:!1})],$.prototype,`events`,void 0),V([R()],$.prototype,`run`,void 0),V([R({attribute:!1})],$.prototype,`stream`,void 0),V([R({attribute:`base-url`})],$.prototype,`baseUrl`,void 0),V([R({attribute:!1})],$.prototype,`client`,void 0),V([R({type:Boolean})],$.prototype,`live`,void 0),V([R({attribute:!1})],$.prototype,`round`,void 0),V([R({attribute:!1})],$.prototype,`rows`,void 0),V([R({reflect:!0})],$.prototype,`mode`,void 0),V([z()],$.prototype,`version`,void 0),V([z()],$.prototype,`behind`,void 0),V([z()],$.prototype,`bulk`,void 0),V([z()],$.prototype,`unseen`,void 0),V([z()],$.prototype,`pinned`,void 0),V([z()],$.prototype,`revealed`,void 0),V([Yn(`.scroller`)],$.prototype,`scroller`,void 0),$=V([L(`ca-transcript`),N()],$);var Hl=e=>G(e.io)||e.rows.some(G),Ul=e=>!Hl(e)&&(!!e.stream||e.launches.length>0||e.rows.some(K)),Wl=e=>e.live?`running`:e.outcomes.get(e.detail.key)?.outcome??zi(void 0,e.detail.rows),Gl=(e,t)=>e.detail.io.upstream.find(e=>e.outputs.some(e=>e.path===t)),Kl=e=>t=>{let n=Gl(e,t);if(!n)return;let r=n.outputs.find(e=>e.path===t);return{name:U(n),written:!!r?.file.exists,outcome:e.outcomes.get(n.key)?.outcome}};function ql(e){let t=e.detail,n=va(e.outcomes.get(t.key)??{attempts:t.rows,cause:null},e.outcomes,e.run,t=>Gl(e,t)?.key);if(n)return n;let r=ha(t.rows[t.rows.length-1]?.reason)[0],i=r?Gl(e,r.path):void 0;return r?_a(q(r.path,e.run),r.problem,i?{name:U(i)}:void 0):``}function Jl(e){let t=e.detail,n=ha(t.rows[t.rows.length-1]?.reason)[0],r=n?.producer?e.outcomes.get(n.producer):void 0;if(r)return r;let i=n?Gl(e,n.path):void 0;if(i)return i;let a=e.outcomes.get(t.key)?.cause;return a?e.outcomes.get(a):void 0}var Yl=e=>co((e.rounds||1)-1),Xl=(e,t)=>D`<a class="lnk" href="#" @click=${n=>{n.preventDefault(),A(e.host,`ca-open-task`,{key:t.key})}}>${U(t)}</a>`,Zl=new Set([`key`,`rows`,`launches`,`stream`,`task_detail_error`,`definition`,`io`]),Ql=e=>D`<span aria-hidden="true">${e?`✓`:`✕`}</span><span class="sr">${M(e?`passed`:`failed`)}</span>`;function $l(e){let t=e.detail.rows,n=t.filter(K),r=t[t.length-1],i=Wl(e);switch(i){case`running`:return[M(`Running`),`neutral`];case`waiting`:return[M(`Waiting`),`muted`];case`skipped`:return[M(`Skipped`),`muted`];case`not_started`:{let t=ql(e);return[M(t?j`Not started: ${t}`:`Not started`),`attention`]}case`failed`:{let t=q(r?.reason,e.run)||Y(r?.stop);return[n.length>1?M(j`Failed on all ${n.length} attempts: ${t}`):M(j`Failed: ${t}`),`failed`]}}if(!r)return[ro(i),`neutral`];let a=n.filter(e=>!e.ok);if(a.length){let t=q(a[0]?.reason,e.run)||Y(a[0]?.stop);return[a.length===1?M(j`Done on attempt ${n.length} after 1 failed attempt. First failure: ${t}`):M(j`Done on attempt ${n.length} after ${a.length} failed attempts. First failure: ${t}`),`neutral`]}let o=(r.rounds||1)-1+(r.hook_errors??[]).length;if(o>0){let t=[...(r.hook_errors??[]).flat(),...(r.round_errors??[]).flat(),...e.rounds.flatMap(e=>e.rejectedWith)],n=t[0]?Ol(q(t[0],e.run)):``;return n?[M(o===1?j`Done after 1 correction. First failed check: ${n}`:j`Done after ${o} corrections. First failed check: ${n}`),`neutral`]:[M(o===1?`Done after 1 correction`:j`Done after ${o} corrections`),`neutral`]}let s=vo(r.hops);return s?[M(j`Done after a model switch: ${s}`),`neutral`]:[M(`Done`),`neutral`]}function eu(e){for(let t=e.launches.length-1;t>=0;t--){let n=e.launches[t],r=n?hl(n).model:``;if(r)return r}return``}function tu(e,t,n){let r=e.detail,i=e.live,{rows:a,launches:o}=r,s=Hl(r),c=Ul(r),l=a.slice().sort((e,t)=>String(e.ts).localeCompare(String(t.ts))),u=l[l.length-1],d=o[0],f={agent:pl(d?.cmd?d.cmd.split(` `)[0]:u?.agent),model:d?.model||u?.model||eu(e),role:d?.role||``},p=c?[...new Set(l.map(e=>e.model).filter(e=>!!e&&e!==f.model))]:[],m=a[0],h=a.filter(K),g=Object.entries(r).filter(([e])=>!Zl.has(e)),[_,v]=$l(e),y=M(s?`Python task`:`Agent task`),b=e.plan?.nodes.find(e=>e.key===r.key);return D`<div class="taskmeta">
      <div class="tm-head">
        ${X(s,y,`tm-av ${s?`py`:``}`)}
        <div style="min-width:0">
          <div class="tm-name" title=${t}>${m?U(m):b?U(b):t.replace(/^python:/,``)} ${i?kn({text:M(`running`),tone:`running`}):O}</div>
          <div class="verdict" data-tone=${sn(v)}>${_}</div>
          ${c?D`<div class="whos">
                ${Pl(f)}${nu(h)}
                ${p.length?D`<span class="meta">${p.length===1?M(j`Earlier attempts used model ${p[0]??``}`):M(j`Earlier attempts used models ${Lr(p)}`)}</span>`:O}
              </div>`:O}
          ${o.length?D`<div class="meta">${o.length===1?M(`1 agent session running`):M(j`${o.length} agent sessions running`)}</div>`:O}
          ${iu(oa(a))}
          ${au(e,h)}
        </div>
      </div>
      ${h.length?D`<div class="runchips">${so(h).map((t,n)=>ou(e,h[n],t,c))}</div>`:O}
      ${ru(h,n)}
      ${Br(h)?D`<div class="meta unread" title=${M(`Event types from the coding agent that this contraagent version does not recognize`)}>
            <span aria-hidden="true">⚠</span> ${M(j`Unrecognized events: ${Br(h)}`)}
          </div>`:O}
      ${r.task_detail_error?D`<div class="meta v-bad">${M(j`The task_detail callback failed: ${r.task_detail_error??``}`)}</div>`:O}
      ${o.map(e=>D`<details class="launch">
          <summary>${H(M(j`Process ${e.pid??`—`}`),e.key||``)}</summary>
          <div class="meta">${H(M(j`Plugin ${e.plugin||M(`none`,{id:`none`,desc:`An empty value`})}`),M(j`Model ${e.model||`—`}`),M(j`Role ${e.role||M(`none`,{id:`none`,desc:`An empty value`})}`))}</div>
        </details>`)}
      ${g.map(([e,t])=>D`<details class="io-fold"><summary>${e}</summary><cae-json-tree .value=${t}></cae-json-tree></details>`)}
    </div>`}function nu(e){let t=[...new Set(e.flatMap(e=>[...(e.hops??[]).map(e=>e.credential),e.credential]).filter(e=>!!e))];return t.length?D`<span class="who ident" title=${[M(`What the coding agent authenticated as: an account or an API key (credential)`),...t.map(go)].filter(Boolean).join(`
`)}
        ><span class="who-l">${M(`identity`)}</span>${Lr(t.map(ho))}</span
      >`:O}function ru(e,t){let n=e.flatMap(e=>e.web_queries??[]),r=new Map;return n.length?D`<details class="io-fold">
        <summary>${n.length===1?M(`1 web search`):M(j`${n.length} web searches`)}</summary>
        <ol class="meta searches">
          ${n.map(e=>{let n=r.get(e)??0;return r.set(e,n+1),D`<li><button class="qlink jmono" @click=${()=>t(e,n)}>
              ${e}
            </button></li>`})}
        </ol>
      </details>`:O}function iu(e){return e?D`<div class="spend">
    <b title=${M(`Reported by the coding agent`)}>${zr(e.cost)}</b>
    <span>${M(j`Tokens: ${W(e.input)} input, ${W(e.output)} output, ${W(e.cache_read)} cache read, ${W(e.cache_creation)} cache write`)}</span>
    <span>${e.calls===1?M(`1 API call`):M(j`${e.calls} API calls`)}</span>
  </div>`:O}function au(e,t){let n=fa(e.journal.length?e.journal:t),r=t[0],i=t[t.length-1],a=r?ma(r,n).start:null;if(!a||!i)return O;let o=ma(i,n).next;return D`<div class="spend quota">
    <span title=${Co(a)}>${M(j`Usage at session start: ${So(a)}`)}</span>
    ${o?D`<span title=${Co(o)}>${M(j`Usage after this task: ${So(o)}`)}</span>`:O}
  </div>`}function ou(e,t,n,r){let i=t.ok,a=q(t.reason,e.run),o=vo(t.hops),s=[M(j`Ended ${Mr(t.ts,!0)}`),Yl(t),r&&t.model?M(j`Model ${t.model}`):``,o?M(j`Model switch: ${o}`):``,a,t.route||``].filter(Boolean).join(`
`),c=t.cost_usd!==null&&t.cost_usd!==void 0?zr(t.cost_usd):``;return D`<span class="runchip ${i?`ok`:`bad`}" title=${s}>
    ${Ql(i)} ${H(n,Y(t.stop,t.reason),P(t.wall_s),c)}
  </span>`}function su(e){let t=e.detail,n=Wl(e);if(n===`not_started`){let t=Jl(e);return D`<div class="blank notrans"><span class="ic" aria-hidden="true">⊘</span><b>${H(M(`No transcript`),ro(n))}</b>
      ${t?D`<span>${M(D`Earlier task ${Bo(e.host,U(t),t)}`)}</span>`:O}</div>`}return Ul(t)?D`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${M(`No transcript`)}</b>
      <span>${M(`Transcript not saved (keep_transcripts = false)`)}</span></div>`:D`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${H(M(`No transcript`),ro(n))}</b></div>`}function cu(e,t,n=``,r={}){let i=t===`output`?D`${Pa(e.status)}${(e.rounds??0)>1?D` <span class="meta" title=${xa()}>${Sa(e.rounds,e.status===`valid`)}</span>`:O}`:Na(e),a=D`<div class="io-hd">${r.chip??i}<span class="jmono ct-path" title=${e.path}>${q(e.path,n)}</span></div>${r.origin?D`<div class="meta io-from">${r.origin}</div>`:O}`;if(t===`output`&&e.status===`refused`)return D`<div class="io-card one">${a}<div class="meta">${Ca(e,n,r.producerOf)}</div></div>`;if(t===`output`&&e.status===`failed`&&!e.file.exists)return D`<div class="io-card one">${a}</div>`;let o=e.errors??[];return D`<div class="io-card">
    ${a}
    ${Ga(e,t)}
    ${Ba(e)}
    ${o.length?D`<h4>${M(`Errors`)}</h4><pre class="ct-err">${o.map(e=>q(e,n)).join(`
`)}</pre>`:O}
  </div>`}var lu=e=>!e.file.exists||e.status!=null&&e.status!==`valid`;function uu(e){let t=new Set(e.inputs.map(e=>e.path)),n=e.inputs.map(t=>{for(let n of e.upstream){let e=n.outputs.find(e=>e.path===t.path);if(e)return{spec:t,from:n,out:e}}return{spec:t,from:null,out:null}}),r=e.upstream.map(e=>({task:e,read:e.outputs.filter(e=>t.has(e.path)).length,rest:e.outputs.filter(e=>!t.has(e.path))})),i=e=>Number(e.task.outputs.some(lu));return{files:n,earlier:[...r].sort((e,t)=>i(t)-i(e))}}var du=e=>typeof e==`string`?e:JSON.stringify(e)??String(e),fu=(e,t)=>{try{return JSON.stringify(e)===JSON.stringify(t)}catch{return!1}},pu=e=>kn({text:ro(e),tone:ka(e),mark:ja(e)});function mu(e){let t=e.detail,n=t.io,r=Object.entries(n.params),{files:i,earlier:a}=uu(n),o=e=>n.upstream.find(t=>t.outputs.some(t=>t.file.exists&&fu(t.file.content,e)));return D`<h4 class="sect-h">${M(`Parameters`)}</h4>
    ${r.length?D`<table class="ct-fields params">
          ${r.map(([t,n])=>{let r=o(n);return D`<tr>
              <td class="jmono">${t}</td>
              <td>${typeof n==`object`&&n?D`<cae-json-tree .value=${n} .open=${0}></cae-json-tree>`:D`<span class="jmono">${du(n)}</span>`}</td>
              <td>${r?D`<span class="from">${M(D`From ${Xl(e,r)}`)}</span>`:O}</td>
            </tr>`})}
        </table>`:D`<div class="meta">${M(`No parameters`)}</div>`}
    <h4 class="sect-h">${M(`Input files`)}</h4>
    ${i.length?i.map(t=>hu(e,t)):D`<div class="meta">${M(`No input files`)}</div>`}
    <h4 class="sect-h">${M(`Earlier tasks`)}</h4>
    ${a.length?a.map(t=>gu(e,t)):D`<div class="meta">${M(`No earlier tasks`)}</div>`}
    ${Hl(t)?O:_u(e)}`}function hu(e,t){let n=t.from,r=n?e.outcomes.get(n.key)?.outcome:void 0,i=n?D`<span>${M(D`Output of ${Xl(e,n)}`)}</span>${r&&r!==`done`?pu(r):O}`:M(`File from before the run`),a=t.out?.status;if(!a)return cu(t.spec,`input`,e.run,{origin:i});let o=Pa(a);return cu({...t.spec,status:a},`input`,e.run,{origin:i,chip:o})}function gu(e,t){let n=t.task,r=G(n)?M(`Python task`):M(`Agent task`),i=e.outcomes.get(n.key)?.outcome,a=n.outputs.length,o=a?H(M(a===1?`1 output file`:j`${a} output files`),t.read?t.read===1?M(`1 read by this task`):M(j`${t.read} read by this task`):``):M(`No output files`),s=D`<div class="up-hd">
    ${X(G(n),r)}
    ${Xl(e,n)}
    ${i?pu(i):O}
    <span class="meta">${o}</span>
  </div>`;if(!t.rest.length)return D`<div class="upstream">${s}</div>`;let c=t.rest.map(t=>cu(t,`output`,e.run,{producerOf:Kl(e)}));return t.rest.some(lu)?D`<div class="upstream">${s}${c}</div>`:D`<details class="upstream"><summary>${s}</summary>${c}</details>`}function _u(e){let t=e.detail,n=e.launches.length,r=e.shownRound,i=e.rounds[r],a=e.rounds[e.rounds.length-1]?.tryNo??1,o=t.rows.filter(K),s=so(o),c=ji(o),l=e.launches[r]?.prompt??``,u=Wl(e);return D`<h4 class="sect-h">${M(`Prompt`)}${n>1&&i?D` <span class="meta">${cl(i,a,s[i.tryNo-1])}: ${ll(i,c[i.tryNo-1]!==c[i.tryNo-2])}</span>`:O}</h4>
    ${l?sl(l):D`<div class="meta">${t.stream?M(`Loading…`):Ul(t)?M(`Prompt not saved (keep_transcripts = false)`):H(M(`No prompt`),ro(u))}</div>`}`}function vu(e,t){let n=t.filter(e=>K(e)&&(e.usage||e.cost_usd!==null&&e.cost_usd!==void 0));if(!n.length)return O;let r=D`<td class="jdim">—</td>`,i=fa(e.journal.length?e.journal:t),a=n.some(e=>(e.quota??[]).length),o=D`<td class="l jdim">—</td>`,s=(e,t)=>e?D`<td class="l" title=${Co(e)}>${(e.credential??``)===(t??``)?So(e):wo(e)}</td>`:o;return D`<h4 class="sect-h">${M(`Tokens and cost`)}</h4>
    <div class="usage-wrap"><table class="usage">
      <tr>
        <th class="l"></th><th>${M(`Input`)}</th><th>${M(`Output`,{id:`tokens-output`,desc:`Column: output tokens`})}</th><th>${M(`Cache read`)}</th><th>${M(`Cache write`)}</th>
        <th>${M(`API calls`)}</th><th title=${M(`Reported by the coding agent`)}>${M(`Cost`)}</th><th class="l">${M(`Identity`)}</th>
        ${a?D`<th class="l" title=${M(`Subscription usage when the agent session started (account-wide)`)}>${M(`Usage at start`)}</th>
              <th class="l" title=${M(`The first reading of the same account after this attempt ended`)}>${M(`Usage after`)}</th>`:O}
      </tr>
      ${n.map(e=>{let t=e.usage,n=e.hops??[];return D`<tr>
            <td class="l">${oo(e.attempt)}</td>
            ${t?D`<td>${W(t.input)}</td><td>${W(t.output)}</td><td>${W(t.cache_read)}</td><td>${W(t.cache_creation)}</td><td>${t.calls}</td>`:D`${r}${r}${r}${r}${r}`}
            <td>${zr(e.cost_usd)}</td><td class="l" title=${go(e.credential)||O}>${ho(e.credential)||`—`}</td>
            ${a?D`${s(ma(e,i).start,e.credential)}${s(ma(e,i).next,e.credential)}`:O}
          </tr>
          ${n.length>1?n.map(e=>D`<tr class="hop">
                  <td class="l">${H(e.model||e.route||`—`,Y(e.stop))}</td>
                  <td></td><td></td><td></td><td></td><td></td>
                  <td>${zr(e.cost_usd)}</td><td class="l" title=${go(e.credential)||O}>${ho(e.credential)||`—`}</td>
                  ${a?D`<td></td><td></td>`:O}
                </tr>`):O}`})}
    </table></div>`}function yu(e){let t=e.detail,n=t.io,r=t.rows[t.rows.length-1];return D`<h4 class="sect-h">${M(`Output files`)}</h4>
    ${n.outputs.length?n.outputs.map(t=>cu(t,`output`,e.run,{producerOf:Kl(e)})):D`<div class="meta">${M(`No output files`)}</div>`}
    ${r?D`<h4 class="sect-h">${M(`Outcome`)}</h4>
          <div class="ct-in">
            ${kn({text:Y(r.stop,r.reason),tone:Oa(r.stop)})}
            ${K(r)?D`<span class="meta">${H(oo(r.attempt),P(r.wall_s),Yl(r))}</span>`:O}

          </div>`:O}
    ${vu(e,t.rows)}
    <h4 class="sect-h">${M(`Later tasks`)}</h4>
    ${n.downstream.length?D`<div class="down">${n.downstream.map(t=>Bo(e.host,U(t),t))}</div>`:D`<div class="meta">${M(`No later tasks`)}</div>`}`}var bu=e=>D`<ca-definition .definition=${e.detail.definition??null} memory="task-definition"></ca-definition>`,xu=w`
  :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
  .taskmeta { flex: none; background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
    border-radius: 14px; padding: 10px 12px; margin-bottom: 8px; color: var(--text-2); }
  .tm-head { display: flex; gap: 12px; align-items: center; }
  .tm-av { width: 36px; height: 36px; border-radius: 11px; display: grid; place-items: center; font-size: 16px; flex: none;
    background: var(--agent-bg); color: var(--agent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--agent) 35%, transparent); }
  .tm-av.py { background: var(--raise); color: var(--text-muted); box-shadow: none; }
  .tm-name { font-size: 15px; font-weight: 600; color: var(--text); display: flex; gap: 8px; align-items: center; }
  .verdict { font-size: 12.5px; color: var(--text); margin-top: 2px; }
  .verdict[data-tone='failed'], .verdict[data-tone='attention'] { color: var(--tone); }
  .verdict[data-tone='muted'] { color: var(--text-muted); }
  .whos { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
  .runchips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .who.ident { color: var(--text-2); font-family: var(--mono); font-weight: 500; }
  .spend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 6px; font-size: 12px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .spend b { color: var(--text); font-weight: 600; }
  .spend.quota { flex-direction: column; gap: 0; }
  .usage-wrap { overflow-x: auto; margin: 4px 0 12px; }
  /* sized to its content (a full-width table spreads a few numbers far apart); the wrap scrolls when it is wider */
  .usage { width: auto; border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }
  .usage th { text-align: right; font-weight: 600; color: var(--text-muted); font-size: 10.5px; white-space: nowrap;
    padding: 6px 14px; border-bottom: 1px solid var(--line2); vertical-align: bottom; }
  .usage td { text-align: right; padding: 8px 14px; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: baseline; }
  .usage th:first-child, .usage td:first-child { padding-left: 4px; }
  .usage td.l.jmono { font-size: 12px; }
  /* the subscription readings wrap at a narrow width rather than push the table past the edge */
  .usage td.l:not(:first-child):not(.jmono) { white-space: normal; min-width: 12ch; }
  .usage th.l, .usage td.l { text-align: left; }
  .usage tr.hop td { padding-top: 4px; padding-bottom: 4px; color: var(--text-muted); }
  .usage tr.hop td:first-child { padding-left: 28px; }
  .runchip { font-size: 11px; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--line2); color: var(--text-2); }
  .runchip.ok > [aria-hidden] { color: var(--status-done); font-weight: 700; }
  .runchip.bad { border-color: color-mix(in srgb, var(--status-failed) 45%, transparent); color: var(--status-failed); background: var(--status-failed-bg); }
  .io-fold { margin-top: 6px; }
  .io-fold > summary, .launch > summary { cursor: pointer; color: var(--text-muted); }
  .searches { margin: 4px 0 0; padding-left: 22px; }
  .unread { color: var(--status-attention); margin-top: 4px; }
  .qlink { background: none; border: 0; padding: 0; color: var(--accent); cursor: pointer; text-align: left; font: inherit; }
  .qlink:hover { text-decoration: underline; }

  .tviews { flex: none; display: flex; gap: 4px; margin: 2px 0 8px; border-bottom: 1px solid var(--line); }
  .tview { background: none; border: 0; border-bottom: 2px solid transparent; color: var(--text-muted); padding: 6px 14px; cursor: pointer; }
  .tview:hover { color: var(--text-2); }
  .tview.sel { color: var(--text); border-bottom-color: var(--accent); }
  .tview .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--text-2); }

  .pane { flex: 1 1 auto; min-height: 0; overflow: auto; }
  .upstream { margin-bottom: 12px; }
  .up-hd { display: flex; align-items: center; gap: 10px; margin: 2px 0 6px; }
  .down { display: flex; flex-wrap: wrap; gap: 8px; }
  .notrans { flex: 1 1 auto; border: 1px solid var(--line); border-radius: 14px; }
  details.upstream > summary { cursor: pointer; list-style: none; }
  details.upstream > summary::-webkit-details-marker { display: none; }
  .params td { vertical-align: top; }
  .from { color: var(--text-muted); white-space: nowrap; }
`,Su=()=>({transcript:M(`Transcript`),input:M(`Input`),output:M(`Output`,{id:`view-output`,desc:`Tab: the files a task wrote`}),definition:M(`Definition`)}),Cu=class extends k{constructor(...e){super(...e),this.baseUrl=``,this.run=``,this.taskKey=null,this.view=`transcript`,this.round=null,this.live=!1,this.journal=[],this.plan=null,this.detail=new ol(this),this.launches=[],this.shownRound=-1,this.rounds=[],this.outcomes=new Map}static{this.styles=[I,qa,Fl,es,xu]}willUpdate(e){(e.has(`run`)||e.has(`taskKey`)||e.has(`client`))&&(this.detail.load(this.client,this.run,this.taskKey),this.launches=[],this.shownRound=-1,this.rounds=[]),this.outcomes=this.plan?Zi(this.journal,this.plan).outcomes:new Map}shownView(e){return this.view===`transcript`&&Hl(e)&&!e.stream?`output`:this.view}revealSearch(e,t){let n=this.transcriptEl?.revealWebSearch(e,t);A(this,`ca-navigate`,n?{view:`transcript`,round:n.round}:{view:`transcript`})}render(){let e=this.taskKey;if(!e)return D`<div class="blank"><span class="ic" aria-hidden="true">✦</span><b>${M(`No task selected`)}</b></div>`;let t=this.detail.value;if(!t)return D`<div class="taskmeta meta"><strong>${e}</strong> ${M(`Loading…`)}</div>`;let n={host:this,run:this.run,detail:t,live:t.launches.length>0&&this.live,journal:this.journal,plan:this.plan,outcomes:this.outcomes,launches:this.launches,shownRound:this.shownRound,rounds:this.rounds},r=this.shownView(t);return D`${tu(n,e,(e,t)=>this.revealSearch(e,t))} ${this.renderViews(t,r)}
      ${t.stream?D`<ca-transcript .run=${this.run} .stream=${t.stream} base-url=${this.baseUrl} .client=${this.client} .live=${n.live}
            .rows=${t.rows} .round=${this.round} mode=${r===`transcript`?`full`:r===`input`?`tabs`:`none`}
            @ca-rounds=${e=>{this.launches=e.detail.launches,this.shownRound=e.detail.shown,this.rounds=e.detail.rounds}}></ca-transcript>`:r===`transcript`?su(n):O}
      ${r===`transcript`?O:D`<div class="pane">${this.renderPane(n,r)}</div>`}`}renderViews(e,t){let n=e.io,r=Hl(e)&&!e.stream,i={input:new Set([...n.inputs.map(e=>e.path),...n.upstream.flatMap(e=>e.outputs.map(e=>e.path))]).size+Object.keys(n.params).length,output:n.outputs.length};return D`<div class="tviews" role="tablist">
      ${lt.filter(e=>!(r&&e===`transcript`)).map(e=>{let n=Su()[e];return D`<button type="button" role="tab" aria-selected=${e===t} class="tview ${e===t?`sel`:``}"
          @click=${()=>A(this,`ca-navigate`,{view:e})}>
          ${n}${i[e]?D`<span class="badge">${i[e]}</span>`:O}
        </button>`})}
    </div>`}renderPane(e,t){return t===`input`?mu(e):t===`output`?yu(e):bu(e)}};V([R({attribute:!1})],Cu.prototype,`client`,void 0),V([R({attribute:`base-url`})],Cu.prototype,`baseUrl`,void 0),V([R()],Cu.prototype,`run`,void 0),V([R({attribute:!1})],Cu.prototype,`taskKey`,void 0),V([R()],Cu.prototype,`view`,void 0),V([R({attribute:!1})],Cu.prototype,`round`,void 0),V([R({type:Boolean})],Cu.prototype,`live`,void 0),V([R({attribute:!1})],Cu.prototype,`journal`,void 0),V([R({attribute:!1})],Cu.prototype,`plan`,void 0),V([Yn(`ca-transcript`)],Cu.prototype,`transcriptEl`,void 0),V([z()],Cu.prototype,`launches`,void 0),V([z()],Cu.prototype,`shownRound`,void 0),V([z()],Cu.prototype,`rounds`,void 0),Cu=V([L(`ca-task-view`),N()],Cu);function wu({snap:e,route:t,derived:n,q:r,client:i,baseUrl:a}){let{state:o}=e;if(!t.run)return D`<div class="blank"><span class="ic" aria-hidden="true">✦</span><b>${M(`No runs yet`,{id:`no-runs-yet`})}</b></div>`;let s=Ni(e.runs,e.run),c=Pi(o,s);switch(t.tab){case`overview`:return D`<ca-overview .state=${o} .summary=${s} .info=${e.info} .run=${t.run} .layer=${t.layer} .unit=${t.unit} .sel=${t.sel}></ca-overview>`;case`tasks`:return D`<ca-task-table .run=${t.run} .journal=${o.journal} .plan=${o.plan} .kind=${t.kind} .q=${r} ?live=${c}></ca-task-table>`;case`journal`:return D`<ca-journal-table .run=${t.run} .rows=${o.journal} .plan=${o.plan} .fresh=${e.fresh} .kind=${t.kind} .stop=${t.stop} .q=${r}></ca-journal-table>`;case`outputs`:return D`<ca-contracts .run=${t.run} .outputs=${o.outputs} .journal=${o.journal} .plan=${o.plan}></ca-contracts>`;case`definitions`:return D`<ca-definitions .client=${i} .run=${t.run} .journal=${o.journal} .plan=${o.plan} .live=${c}
        .selected=${t.def}></ca-definitions>`;case`procs`:return D`<ca-procs-view .procs=${o.procs}></ca-procs-view>`;case`stream`:return D`<ca-task-view .client=${i} .journal=${o.journal} .plan=${o.plan} base-url=${a} .run=${t.run}
        .taskKey=${t.key??Ji(n.rows)} .view=${t.view} .round=${t.round} .live=${c}></ca-task-view>`;default:{let n=t.tab.slice(6);return D`<ca-panel-view .name=${n} .panel=${e.info.panels.find(e=>e.name===n)} .data=${o.panels[n]}></ca-panel-view>`}}}var Tu=class extends k{constructor(){super(),new mn(this)}createRenderRoot(){return this}render(){return new Date().toLocaleTimeString(en(),{hour12:!1})}};Tu=V([L(`ca-clock`),N()],Tu);var Eu=e=>na(e),Du=e=>{let t=Date.parse(e.last_ts||``);return Number.isNaN(t)?1/0:(Date.now()-t)/1e3},Ou=class extends k{constructor(...e){super(...e),this.runs=[],this.current=``,this.open=!1,this.q=``,this.kb=-1}static{this.styles=[I,w`
      :host { position: absolute; top: 50px; width: min(580px, calc(100vw - 24px)); max-height: min(72vh, 660px);
        display: flex; flex-direction: column; background: var(--panel); border: 1px solid var(--line2); border-radius: 14px;
        box-shadow: 0 24px 70px color-mix(in srgb, var(--shadow) 70%, transparent); opacity: 0; transform: translateY(-6px) scale(0.985);
        pointer-events: none; z-index: 40; transition: opacity 0.16s var(--ease), transform 0.16s var(--ease); }
      :host([open]) { opacity: 1; transform: none; pointer-events: auto; }
      .search { padding: 10px; border-bottom: 1px solid var(--line); }
      input { width: 100%; background: var(--well); border: 1px solid var(--line); color: var(--text); border-radius: 9px;
        padding: 8px 11px; font: inherit; outline: none; }
      input:focus { border-color: var(--accent); }
      .list { overflow: auto; padding: 6px; }
      .group { font-size: 11.5px; font-weight: 600; color: var(--text-muted); padding: 10px 9px 4px; }
      .group .n { font-weight: 400; margin-left: 4px; }
      .keys { margin-top: 6px; display: flex; gap: 4px; align-items: center; }
      .item { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; gap: 3px 10px; align-items: center;
        padding: 7px 9px; border-radius: 9px; cursor: pointer; }
      .item:hover, .item.kb { background: var(--raise); }
      .item.cur { box-shadow: inset 2px 0 0 var(--accent); background: var(--accent-bg); }
      .nm { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .when { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
      .sub { grid-column: 2 / 4; display: flex; gap: 7px; flex-wrap: wrap; font-size: 11px; color: var(--text-muted); }
    `]}updated(e){e.has(`open`)&&this.open&&(this.q=``,this.kb=-1,setTimeout(()=>this.input?.focus(),30))}visible(){let e=this.q.toLowerCase().trim(),t=this.runs.filter(t=>!e||t.run.toLowerCase().includes(e)||(t.run_group||``).toLowerCase().includes(e));return[...t.filter(e=>e.running),...t.filter(e=>!e.running&&Du(e)<86400),...t.filter(e=>!e.running&&Du(e)>=86400)]}pick(e){this.close(),e!==this.current&&A(this,`ca-select-run`,{run:e})}close(){A(this,`ca-close`,{})}onKey(e,t){if(e.key===`Escape`)return this.close();if(e.key===`ArrowDown`)this.kb=Math.min(t.length-1,this.kb+1);else if(e.key===`ArrowUp`)this.kb=Math.max(0,this.kb-1);else if(e.key===`Enter`){let e=t[Math.max(0,this.kb)];e&&this.pick(e.run);return}else return;e.preventDefault(),this.updateComplete.then(()=>this.renderRoot.querySelector(`.item.kb`)?.scrollIntoView({block:`nearest`}))}render(){let e=this.visible(),t=[[M(`Running`),e.filter(e=>e.running)],[M(`Last 24 hours`),e.filter(e=>!e.running&&Du(e)<86400)],[M(`Older`),e.filter(e=>!e.running&&Du(e)>=86400)]],n=0;return D`<div class="search">
        <input placeholder=${M(`Search runs`)} aria-label=${M(`Search runs`)} autocomplete="off" .value=${this.q}
          @input=${e=>{this.q=e.target.value,this.kb=0}}
          @keydown=${t=>this.onKey(t,e)} />
        <div class="keys meta" aria-hidden="true"><span class="kbd">↑</span><span class="kbd">↓</span> <span class="kbd">Enter</span> <span class="kbd">Esc</span></div>
      </div>
      <div class="list" role="listbox">
        ${e.length?t.map(([e,t])=>t.length?D`<div class="group">${e} <span class="n">${t.length}</span></div>
                    ${t.map(e=>this.item(e,n++))}`:O):D`<div class="blank"><span>${M(`No runs match`)}</span></div>`}
      </div>`}counts(e){let t=e.tasks,n=[M(j`${t.done} of ${t.total} tasks done`)];t.failed&&n.push(J(`failed`,t.failed)),t.not_started&&n.push(J(`not_started`,t.not_started)),t.skipped&&n.push(J(`skipped`,t.skipped)),t.running&&n.push(J(`running`,t.running)),t.waiting&&n.push(J(`waiting`,t.waiting));let r=Eu(e);r!=null&&n.push(M(j`took ${P(r)}`)),e.cost_usd!==null&&e.cost_usd!==void 0&&n.push(zr(e.cost_usd));let i=To(e.quota??[]);return i&&n.push(i),H(...n)}item(e,t){let n=Ta(e.running,e.tasks);return D`<div class=${`item${e.run===this.current?` cur`:``}${t===this.kb?` kb`:``}`} role="option" aria-selected=${e.run===this.current} @click=${()=>this.pick(e.run)}>
      <span class="dot" data-tone=${sn(n)} aria-hidden="true"></span><span class="nm">${e.run}</span>
      <span class="when" title=${Mr(e.last_ts,!0)}>${e.running?M(`running`):Nr(e.last_ts)}</span>
      <span class="sub">
        ${e.run_group&&e.run_group!==e.run?D`<span>${M(j`Run group ${e.run_group}`)}</span>`:O}
        <span title=${Eo(e.quota??[])}>${this.counts(e)}</span>
      </span>
    </div>`}};V([R({attribute:!1})],Ou.prototype,`runs`,void 0),V([R()],Ou.prototype,`current`,void 0),V([R({type:Boolean,reflect:!0})],Ou.prototype,`open`,void 0),V([z()],Ou.prototype,`q`,void 0),V([z()],Ou.prototype,`kb`,void 0),V([Yn(`input`)],Ou.prototype,`input`,void 0),Ou=V([L(`ca-run-picker`),N()],Ou);function ku(e){return e===`system`?M(`System`):e===`high-contrast`?M(`High contrast`):s[e].label}var Au=e=>{let t=s[e].tokens;return D`<span class="sw" style="background:${t.card};border-color:${t.line2}"
    ><i style="background:${t.accent}"></i><i style="background:${t[`code-string`]}"></i><i style="background:${t[`code-keyword`]}"></i
  ></span>`},ju=class extends k{constructor(...e){super(...e),this.value=`contraagent-dark`,this.system=`contraagent-dark`,this.open=!1,this.onDocDown=e=>{this.open&&!e.composedPath().includes(this)&&(this.open=!1)}}static{this.styles=[I,w`
      :host { position: relative; display: inline-flex; }
      .trig { display: inline-flex; align-items: center; gap: 6px; background: none; border: 1px solid var(--line); border-radius: 999px;
        padding: 2px 10px 2px 7px; font-size: 11px; color: var(--text-muted); cursor: pointer; }
      .trig:hover, .trig[aria-expanded='true'] { color: var(--text); border-color: var(--line2); }
      .trig svg { width: 13px; height: 13px; }
      .menu { position: absolute; right: 0; top: calc(100% + 8px); min-width: 236px; padding: 6px; z-index: 50;
        background: var(--panel); border: 1px solid var(--line2); border-radius: 12px;
        box-shadow: 0 18px 48px color-mix(in srgb, var(--shadow) 65%, transparent); animation: enter 0.16s var(--ease) both; }
      .grp { font-size: 11px; color: var(--text-muted); padding: 8px 9px 4px; }
      [role='separator'] { height: 1px; background: var(--line); margin: 6px 4px; }
      .item { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 10px; width: 100%;
        background: none; border: 0; border-radius: 8px; padding: 6px 9px; text-align: left; cursor: pointer; color: var(--text-2); font-size: 12px; }
      .item:hover { background: var(--raise); color: var(--text); }
      .item:focus-visible { outline-offset: -2px; }
      .item[aria-checked='true'] { background: var(--accent-bg); color: var(--text); font-weight: 600; }
      .item .meta { font-weight: 400; }
      .item .sub { display: block; }
      /* a radio mark: a ring, filled for the current choice */
      .rd { width: 12px; height: 12px; border-radius: 50%; border: 1.5px solid var(--line2); display: grid; place-items: center; }
      [aria-checked='true'] .rd { border-color: var(--accent); }
      [aria-checked='true'] .rd::after { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }
      .sw { display: inline-flex; gap: 2px; align-items: flex-end; width: 30px; height: 18px; border-radius: 5px; border: 1px solid; padding: 3px 4px; }
      .sw i { flex: 1; height: 4px; border-radius: 2px; }
      .sw i:first-child { height: 8px; }
      .sw.split { padding: 0; overflow: hidden; gap: 0; }
      .sw.split > span { flex: 1; height: 100%; display: flex; gap: 2px; align-items: flex-end; padding: 3px 2px; }
    `]}connectedCallback(){super.connectedCallback(),document.addEventListener(`pointerdown`,this.onDocDown)}disconnectedCallback(){super.disconnectedCallback(),document.removeEventListener(`pointerdown`,this.onDocDown)}items(){return[...this.renderRoot.querySelectorAll(`.item`)]}updated(e){e.has(`open`)&&this.open&&(this.items().find(e=>e.getAttribute(`aria-checked`)===`true`)??this.items()[0])?.focus()}close(e){this.open=!1,e&&this.trig?.focus()}choose(e){this.value=e,A(this,`ca-choose-theme`,{theme:e}),this.close(!0)}onTrigKey(e){(e.key===`ArrowDown`||e.key===`ArrowUp`)&&(e.preventDefault(),this.open=!0)}onMenuKey(e){let t=this.items(),n=t.indexOf(e.composedPath()[0]),r=e=>t[(e+t.length)%t.length]?.focus();if(e.key===`ArrowDown`)r(n+1);else if(e.key===`ArrowUp`)r(n-1);else if(e.key===`Home`)r(0);else if(e.key===`End`)r(t.length-1);else if(e.key===`Escape`)this.close(!0);else if(e.key===`Tab`){this.open=!1;return}else return;e.preventDefault(),e.stopPropagation()}item(e){let t=e===this.value,n=e===`system`?D`<span class="sw split" style="border-color:${s[`contraagent-dark`].tokens.line2}"
            ><span style="background:${s[`contraagent-dark`].tokens.card}"><i style="background:${s[`contraagent-dark`].tokens.accent}"></i></span
            ><span style="background:${s[`contraagent-light`].tokens.card}"><i style="background:${s[`contraagent-light`].tokens.accent}"></i></span
          ></span>`:Au(e);return D`<button type="button" class="item" role="menuitemradio" aria-checked=${t?`true`:`false`} tabindex="-1"
      data-theme=${e} @click=${()=>this.choose(e)}>
      ${n}<span>${ku(e)}${e===`system`?D`<span class="meta sub">${s[this.system].label}</span>`:O}</span><span class="rd" aria-hidden="true"></span>
    </button>`}render(){let e=r.filter(e=>e===`system`||!i.includes(e));return D`<button type="button" class="trig" aria-haspopup="menu" aria-expanded=${this.open?`true`:`false`} aria-controls="menu"
        title=${M(j`Theme: ${ku(this.value)}`)} @click=${()=>this.open=!this.open} @keydown=${e=>this.onTrigKey(e)}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" stroke-width="1.5" /><path d="M8 1.75a6.25 6.25 0 0 1 0 12.5z" fill="currentColor" /></svg>
        ${M(`Theme`)}
      </button>
      ${this.open?D`<div id="menu" class="menu" role="menu" aria-label=${M(`Theme`)} @keydown=${e=>this.onMenuKey(e)}>
            ${e.map(e=>this.item(e))}
            <div role="separator"></div>
            <div role="group" aria-labelledby="grp-editor">
              <div class="grp" id="grp-editor">${M(`Editor themes`)}</div>
              ${i.map(e=>this.item(e))}
            </div>
          </div>`:O}`}};V([R()],ju.prototype,`value`,void 0),V([R()],ju.prototype,`system`,void 0),V([z()],ju.prototype,`open`,void 0),V([Yn(`.trig`)],ju.prototype,`trig`,void 0),ju=V([L(`ca-theme-switch`),N()],ju);var Mu=250,Nu=class extends k{static{this.styles=[at,I,zo,Po]}constructor(){super(),this.baseUrl=``,this.history=`url`,this.run=``,this.locale=``,this.theme=``,this.live=!1,this.pickerOpen=!1,this.qDraft=null,this.themes=new no(this,{theme:()=>this.theme,pageWide:()=>this.history===`url`}),this.mainScroll=new $a(`main`),this.pendingScroll=null,this.qTimer=null,this.cleanups=[],new eo(this,{locale:()=>this.locale,pageWide:()=>this.history===`url`}),new to(this,e=>this.onKey(e))}connectedCallback(){super.connectedCallback(),this.store=new Li({baseUrl:this.baseUrl}),this.show(this.store.snapshot),this.cleanups.push(this.store.subscribe(e=>{this.show(e),this.pickDefaultRun()}),this.store.onNewRow(e=>this.toasts?.show(...Ao(e,this.snap.run)))),this.router=new gt(this.history,(e,t)=>this.onRoute(e,t),this.run?{run:this.run}:{},ti),this.router.start(),this.store.start();let e=e=>{this.pickerOpen&&!e.composedPath().some(e=>e instanceof HTMLElement&&(e.localName===`ca-run-picker`||e.classList.contains(`runbtn`)))&&(this.pickerOpen=!1)},t=()=>Ro(this.renderRoot);document.addEventListener(`click`,e),addEventListener(`resize`,t),this.cleanups.push(()=>document.removeEventListener(`click`,e),()=>removeEventListener(`resize`,t)),this.addEventListener(`ca-open-task`,e=>{this.navigate({tab:`stream`,key:e.detail.key,...e.detail.view?{view:e.detail.view}:{}})}),this.addEventListener(`ca-navigate`,e=>{let{replace:t,...n}=e.detail;this.navigate(n,{replace:t===!0})}),this.addEventListener(`ca-select-run`,e=>this.navigate({run:e.detail.run})),this.addEventListener(`ca-filter`,e=>this.navigate(e.detail)),this.addEventListener(`ca-choose-theme`,e=>{this.theme=e.detail.theme,_(e.detail.theme)})}show(e){this.snap=e,this.live=Pi(e.state,Ni(e.runs,e.run)),document.title=M(j`${e.info.title} monitor`)}get shownTheme(){return this.themes.shown}disconnectedCallback(){super.disconnectedCallback();for(let e of this.cleanups.splice(0))e();this.router.stop(),this.store.stop(),this.mainScroll.detach()}navigate(e,t={}){this.router.navigate(e,t)}onRoute(e,t){this.route=e,t!==`replace`&&(this.qDraft=null),this.store.selectRun(e.run),this.pickDefaultRun(),t!==`replace`&&(this.pendingScroll=t)}pickDefaultRun(){let e=this.snap.runs[0];!this.route.run&&e&&this.navigate({run:e.run},{replace:!0})}onKey(e){if(e.key===`r`)e.preventDefault(),this.pickerOpen=!0;else if(e.key===`/`)e.preventDefault(),this.renderRoot.querySelector(`.bar input`)?.focus();else if(/^[1-9]$/.test(e.key)){let t=Io(this.snap.info.panels)[Number(e.key)-1];t&&this.navigate({tab:t.id})}}updated(){Ro(this.renderRoot),this.main&&this.mainScroll.attach(this.main),this.pendingScroll&&=(this.pendingScroll===`push`?this.mainScroll.reset():this.mainScroll.restore(),null)}setQ(e){this.qDraft=e,this.qTimer&&clearTimeout(this.qTimer),this.qTimer=setTimeout(()=>{this.qTimer=null,this.navigate({q:e})},Mu)}pickLocale(e){this.locale=e,on(e)}render(){if(!this.snap||!this.route)return O;let{snap:e,route:t}=this,n=Ni(e.runs,e.run),r=Fi(e.state.procs),i=Ta(!!n?.running,n?.tasks),a=Zi(e.state.journal,e.state.plan);return D`
      <header>
        ${Vo(e.info.title)}
        <button type="button" class="runbtn" title=${M(`Switch run (r)`)} @click=${()=>this.pickerOpen=!this.pickerOpen}>
          <span class="dot" data-tone=${sn(i)} aria-hidden="true"></span>
          <span class="rn">${t.run||`—`}</span>
          <span class="rs" title=${n?Eo(Do(e.state,n)):``}>${n?Oo(e.state,n,a):``}</span>
          <span class="chev" aria-hidden="true">▾</span>
        </button>
        <div class="hdr-right">
          ${Ho(this,r)}
          <ca-theme-switch .value=${this.themes.choice} .system=${this.themes.system}></ca-theme-switch>
          <cae-segmented class="langs" label=${M(`Language`)} .value=${en()}
            .options=${Yt.map(e=>({value:e,label:Qt[e],lang:e}))}
            @cae-change=${e=>rn(e.detail.value)&&this.pickLocale(e.detail.value)}></cae-segmented>
          ${Uo(e.connected)}
          <ca-clock class="clock"></ca-clock>
        </div>
        <ca-run-picker .runs=${e.runs} current=${t.run} ?open=${this.pickerOpen}
          @ca-close=${()=>this.pickerOpen=!1}></ca-run-picker>
      </header>
      ${this.renderTabs(a,r.length)} ${this.renderBar(a)}
      <main class=${t.tab===`stream`?`stream`:``}>${wu({snap:e,route:t,derived:a,q:this.qDraft??t.q,client:this.store.client,baseUrl:this.baseUrl})}</main>
      <ca-toasts></ca-toasts>
    `}renderTabs(e,t){let{state:n}=this.snap,{tries:r}=e.tries,i=e.counts;return Lo(Io(this.snap.info.panels),this.route.tab,e=>e===`tasks`?[i.total||``,`neutral`]:e===`journal`?[r||``,`neutral`]:e===`procs`?[n.procs?.alive&&t||``,`running`]:null,e=>this.navigate({tab:e}))}renderBar(e){let{route:t}=this;if(t.tab!==`tasks`&&t.tab!==`journal`)return O;let{counts:n,kinds:r}=e,i=n.total;return D`<div class="bar">
      <select title=${M(`Kind`)} aria-label=${M(`Kind`)} @change=${e=>this.navigate({kind:e.target.value})}>
        <option value="" ?selected=${!t.kind}>${M(`All kinds`)}</option>
        ${r.map(e=>D`<option ?selected=${e===t.kind}>${e}</option>`)}
      </select>
      <input placeholder=${M(`Filter`)} aria-label=${M(`Text filter`)} size="22" title=${M(`Text filter (/)`)} .value=${this.qDraft??t.q}
        @input=${e=>this.setQ(e.target.value)} />
      <span class="meta">${t.tab===`journal`?ko(e.tries):M(i===1?`1 task`:j`${i} tasks`)}</span>
    </div>`}};V([R({attribute:`base-url`})],Nu.prototype,`baseUrl`,void 0),V([R()],Nu.prototype,`history`,void 0),V([R()],Nu.prototype,`run`,void 0),V([R()],Nu.prototype,`locale`,void 0),V([R()],Nu.prototype,`theme`,void 0),V([R({type:Boolean,reflect:!0})],Nu.prototype,`live`,void 0),V([z()],Nu.prototype,`snap`,void 0),V([z()],Nu.prototype,`route`,void 0),V([z()],Nu.prototype,`pickerOpen`,void 0),V([z()],Nu.prototype,`qDraft`,void 0),V([Yn(`main`)],Nu.prototype,`main`,void 0),V([Yn(`ca-toasts`)],Nu.prototype,`toasts`,void 0),Nu=V([L(`ca-monitor`),N()],Nu),typeof document<`u`&&st(document);