var e=Object.defineProperty,t=(t,n)=>{let r={};for(var i in t)e(r,i,{get:t[i],enumerable:!0});return n||e(r,Symbol.toStringTag,{value:`Module`}),r},n=globalThis,r=n.ShadowRoot&&(n.ShadyCSS===void 0||n.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,i=Symbol(),a=new WeakMap,o=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==i)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(r&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=a.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&a.set(t,e))}return e}toString(){return this.cssText}},s=e=>new o(typeof e==`string`?e:e+``,void 0,i),c=(e,...t)=>new o(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,i),l=(e,t)=>{if(r)e.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let r of t){let t=document.createElement(`style`),i=n.litNonce;i!==void 0&&t.setAttribute(`nonce`,i),t.textContent=r.cssText,e.appendChild(t)}},u=r?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return s(t)})(e):e,{is:d,defineProperty:f,getOwnPropertyDescriptor:p,getOwnPropertyNames:m,getOwnPropertySymbols:h,getPrototypeOf:g}=Object,_=globalThis,v=_.trustedTypes,y=v?v.emptyScript:``,b=_.reactiveElementPolyfillSupport,x=(e,t)=>e,S={toAttribute(e,t){switch(t){case Boolean:e=e?y:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},C=(e,t)=>!d(e,t),ee={attribute:!0,type:String,converter:S,reflect:!1,useDefault:!1,hasChanged:C};Symbol.metadata??=Symbol(`metadata`),_.litPropertyMetadata??=new WeakMap;var w=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=ee){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&f(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=p(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??ee}static _$Ei(){if(this.hasOwnProperty(x(`elementProperties`)))return;let e=g(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(x(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(x(`properties`))){let e=this.properties,t=[...m(e),...h(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(u(e))}else e!==void 0&&t.push(u(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return l(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?S:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?S:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??C)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};w.elementStyles=[],w.shadowRootOptions={mode:`open`},w[x(`elementProperties`)]=new Map,w[x(`finalized`)]=new Map,b?.({ReactiveElement:w}),(_.reactiveElementVersions??=[]).push(`2.1.2`);var te=globalThis,ne=e=>e,re=te.trustedTypes,ie=re?re.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,ae=`$lit$`,T=`lit$${Math.random().toFixed(9).slice(2)}$`,oe=`?`+T,E=`<${oe}>`,D=document,se=()=>D.createComment(``),ce=e=>e===null||typeof e!=`object`&&typeof e!=`function`,le=Array.isArray,ue=e=>le(e)||typeof e?.[Symbol.iterator]==`function`,de=`[ 	
\f\r]`,fe=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,pe=/-->/g,me=/>/g,he=RegExp(`>|${de}(?:([^\\s"'>=/]+)(${de}*=${de}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),ge=/'/g,_e=/"/g,ve=/^(?:script|style|textarea|title)$/i,ye=e=>(t,...n)=>({_$litType$:e,strings:t,values:n}),O=ye(1),be=ye(2),xe=Symbol.for(`lit-noChange`),k=Symbol.for(`lit-nothing`),Se=new WeakMap,Ce=D.createTreeWalker(D,129);function we(e,t){if(!le(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return ie===void 0?t:ie.createHTML(t)}var Te=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=fe;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===fe?c[1]===`!--`?o=pe:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=he):(ve.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=he):o=me:o===he?c[0]===`>`?(o=i??fe,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?he:c[3]===`"`?_e:ge):o===_e||o===ge?o=he:o===pe||o===me?o=fe:(o=he,i=void 0);let d=o===he&&e[t+1].startsWith(`/>`)?` `:``;a+=o===fe?n+E:l>=0?(r.push(s),n.slice(0,l)+ae+n.slice(l)+T+d):n+T+(l===-2?t:d)}return[we(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},Ee=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=Te(t,n);if(this.el=e.createElement(l,r),Ce.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=Ce.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(ae)){let t=u[o++],n=i.getAttribute(e).split(T),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?je:r[1]===`?`?Me:r[1]===`@`?Ne:Ae}),i.removeAttribute(e)}else e.startsWith(T)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(ve.test(i.tagName)){let e=i.textContent.split(T),t=e.length-1;if(t>0){i.textContent=re?re.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],se()),Ce.nextNode(),c.push({type:2,index:++a});i.append(e[t],se())}}}else if(i.nodeType===8){if(i.data===oe)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(T,e+1))!==-1;)c.push({type:7,index:a}),e+=T.length-1}}a++}}static createElement(e,t){let n=D.createElement(`template`);return n.innerHTML=e,n}};function De(e,t,n=e,r){if(t===xe)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=ce(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=De(e,i._$AS(e,t.values),i,r)),t}var Oe=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??D).importNode(t,!0);Ce.currentNode=r;let i=Ce.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new ke(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new Pe(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=Ce.nextNode(),a++)}return Ce.currentNode=D,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},ke=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=k,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=De(this,e,t),ce(e)?e===k||e==null||e===``?(this._$AH!==k&&this._$AR(),this._$AH=k):e!==this._$AH&&e!==xe&&this._(e):e._$litType$===void 0?e.nodeType===void 0?ue(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==k&&ce(this._$AH)?this._$AA.nextSibling.data=e:this.T(D.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=Ee.createElement(we(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new Oe(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=Se.get(e.strings);return t===void 0&&Se.set(e.strings,t=new Ee(e)),t}k(t){le(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(se()),this.O(se()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=ne(e).nextSibling;ne(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},Ae=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=k,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=k}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=De(this,e,t,0),a=!ce(e)||e!==this._$AH&&e!==xe,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=De(this,r[n+o],t,o),s===xe&&(s=this._$AH[o]),a||=!ce(s)||s!==this._$AH[o],s===k?e=k:e!==k&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===k?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},je=class extends Ae{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===k?void 0:e}},Me=class extends Ae{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==k)}},Ne=class extends Ae{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=De(this,e,t,0)??k)===xe)return;let n=this._$AH,r=e===k&&n!==k||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==k&&(n===k||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Pe=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){De(this,e)}},Fe={M:ae,P:T,A:oe,C:1,L:Te,R:Oe,D:ue,V:De,I:ke,H:Ae,N:Me,U:Ne,B:je,F:Pe},Ie=te.litHtmlPolyfillSupport;Ie?.(Ee,ke),(te.litHtmlVersions??=[]).push(`3.3.3`);var Le=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new ke(t.insertBefore(se(),e),e,void 0,n??{})}return i._$AI(e),i},Re=globalThis,A=class extends w{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Le(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return xe}};A._$litElement$=!0,A.finalized=!0,Re.litElementHydrateSupport?.({LitElement:A});var ze=Re.litElementPolyfillSupport;ze?.({LitElement:A}),(Re.litElementVersions??=[]).push(`4.2.2`);var Be=[`contraagent-dark`,`contraagent-light`,`github-dark`,`github-light`,`one-dark`,`nord`,`high-contrast`],Ve=[`contraagent-dark`,`contraagent-light`,`system`,`github-dark`,`github-light`,`one-dark`,`nord`,`high-contrast`],He=[`github-dark`,`github-light`,`one-dark`,`nord`,`high-contrast`],Ue=`contraagent-dark`,We={dark:`contraagent-dark`,light:`contraagent-light`},Ge=[{name:`backdrop`,prop:`--ca-backdrop`,meaning:`the monitor's page, behind the panels (a colour or a gradient)`},{name:`bg`,prop:`--ca-bg`,meaning:`the page`},{name:`card`,prop:`--ca-card`,meaning:`a card or a graph node`},{name:`panel`,prop:`--ca-panel`,meaning:`a panel (bottom of its gradient)`},{name:`panel2`,prop:`--ca-panel2`,meaning:`a panel (top of its gradient), a sticky header`},{name:`raise`,prop:`--ca-raise`,meaning:`a raised surface: a neutral chip, a hovered row`},{name:`well`,prop:`--ca-well`,meaning:`a sunken surface: code, a graph's frame`},{name:`track`,prop:`--ca-track`,meaning:`the empty part of a bar`},{name:`line`,prop:`--ca-line`,meaning:`a border`},{name:`line2`,prop:`--ca-line2`,meaning:`a stronger border, a graph's edge`},{name:`shadow`,prop:`--ca-shadow`,meaning:`the colour of a shadow under a panel, a menu or a notice`},{name:`text`,prop:`--ca-text`,meaning:`text, and every number that is not a problem count`},{name:`text-2`,prop:`--ca-text-secondary`,meaning:`secondary text`},{name:`text-muted`,prop:`--ca-text-muted`,meaning:`labels, captions, units`},{name:`accent`,prop:`--ca-accent`,meaning:`links, the selected tab or item`},{name:`accent-bg`,prop:`--ca-accent-bg`,meaning:`a selected row or item`,derive:`color-mix(in srgb, var(--accent) calc(var(--tint) + 1%), transparent)`},{name:`focus`,prop:`--ca-focus`,meaning:`the focus ring`},{name:`focus-width`,prop:`--ca-focus-width`,meaning:`the width of the focus ring`},{name:`selection`,prop:`--ca-selection`,meaning:`selected text`},{name:`status-failed`,prop:`--ca-status-failed`,meaning:`failed: a task, an attempt, a check (with ✕)`},{name:`status-failed-bg`,prop:`--ca-status-failed-bg`,meaning:`the tint behind a failed pill or chip`,derive:`color-mix(in srgb, var(--status-failed) var(--tint), transparent)`},{name:`status-attention`,prop:`--ca-status-attention`,meaning:`not failed, needs a look: not started (with ◌), a limit near`},{name:`status-attention-bg`,prop:`--ca-status-attention-bg`,meaning:`the tint behind an attention pill or chip`,derive:`color-mix(in srgb, var(--status-attention) var(--tint), transparent)`},{name:`status-done`,prop:`--ca-status-done`,meaning:`done or passed: marks (✓) and small chips only`},{name:`status-done-bg`,prop:`--ca-status-done-bg`,meaning:`the tint behind a done pill or chip`,derive:`color-mix(in srgb, var(--status-done) var(--tint), transparent)`},{name:`status-running`,prop:`--ca-status-running`,meaning:`running, live`},{name:`status-running-bg`,prop:`--ca-status-running-bg`,meaning:`the tint behind a running pill or chip`,derive:`color-mix(in srgb, var(--status-running) var(--tint), transparent)`},{name:`status-muted`,prop:`--ca-status-muted`,meaning:`skipped, waiting, not run`},{name:`status-muted-bg`,prop:`--ca-status-muted-bg`,meaning:`the tint behind a muted pill or chip`,derive:`color-mix(in srgb, var(--status-muted) calc(var(--tint) - 1%), transparent)`},{name:`tint`,prop:`--ca-tint`,meaning:`how strong a tint is: the share of its colour in a status, agent or selected background`},{name:`agent`,prop:`--ca-agent`,meaning:`identity: an agent task's icon and edge`},{name:`agent-bg`,prop:`--ca-agent-bg`,meaning:`the tint behind an agent task's icon`,derive:`color-mix(in srgb, var(--agent) calc(var(--tint) + 2%), transparent)`},{name:`meter`,prop:`--ca-meter`,meaning:`a bar that measures, not judges: time, usage, progress`},{name:`tok-input`,prop:`--ca-tok-input`,meaning:`tokens: input`},{name:`tok-cache-read`,prop:`--ca-tok-cache-read`,meaning:`tokens: cache read`},{name:`tok-cache-write`,prop:`--ca-tok-cache-write`,meaning:`tokens: cache write`},{name:`tok-output`,prop:`--ca-tok-output`,meaning:`tokens: output`},{name:`code-keyword`,prop:`--ca-code-keyword`,meaning:`code: keywords`},{name:`code-string`,prop:`--ca-code-string`,meaning:`code and JSON: strings`},{name:`code-number`,prop:`--ca-code-number`,meaning:`code and JSON: numbers`},{name:`code-constant`,prop:`--ca-code-constant`,meaning:`code: constants, template placeholders`},{name:`code-comment`,prop:`--ca-code-comment`,meaning:`code: comments`},{name:`code-function`,prop:`--ca-code-function`,meaning:`code: functions, decorators`},{name:`code-type`,prop:`--ca-code-type`,meaning:`code: classes and types`},{name:`code-name`,prop:`--ca-code-name`,meaning:`code: built-ins; JSON: keys`}],Ke={"contraagent-dark":{label:`contraagent Dark`,scheme:`dark`,tokens:{backdrop:`radial-gradient(1100px 520px at 8% -12%, #10203a 0%, transparent 62%), radial-gradient(900px 480px at 108% 4%, #1b1238 0%, transparent 58%), #060a11`,bg:`#060a11`,card:`#0f1724`,panel:`#0f1724`,panel2:`#142034`,raise:`#1a2740`,well:`#0a111c`,track:`#1b273b`,line:`#1d2940`,line2:`#2b3c58`,shadow:`#060a11`,text:`#e7edf5`,"text-2":`#bcc7d6`,"text-muted":`#909db2`,accent:`#7aa2ff`,focus:`#7aa2ff`,"focus-width":`2px`,selection:`#7aa2ff4d`,"status-failed":`#f87171`,"status-attention":`#fbbf24`,"status-done":`#34d399`,"status-running":`#22d3ee`,"status-muted":`#94a3b8`,tint:`13%`,agent:`#b597fb`,meter:`#7d8ba3`,"tok-input":`#7c86f5`,"tok-cache-read":`#3f4d63`,"tok-cache-write":`#8796ad`,"tok-output":`#d6b8ff`,"code-keyword":`#c4a5ff`,"code-string":`#7ee2a8`,"code-number":`#f5c26b`,"code-constant":`#ff9e64`,"code-comment":`#74839a`,"code-function":`#7dd3fc`,"code-type":`#ffd479`,"code-name":`#79b8ff`}},"contraagent-light":{label:`contraagent Light`,scheme:`light`,tokens:{backdrop:`radial-gradient(1100px 520px at 8% -12%, #dde7fb 0%, transparent 62%), radial-gradient(900px 480px at 108% 4%, #ebe3fa 0%, transparent 58%), #eef2f8`,bg:`#eef2f8`,card:`#ffffff`,panel:`#ffffff`,panel2:`#f7f9fc`,raise:`#e6ecf5`,well:`#f3f6fa`,track:`#e1e7f0`,line:`#d6dde8`,line2:`#b6c2d3`,shadow:`#0f172438`,text:`#0f1724`,"text-2":`#34415a`,"text-muted":`#556279`,accent:`#2f58d4`,focus:`#2f58d4`,"focus-width":`2px`,selection:`#2f58d42e`,"status-failed":`#b8132d`,"status-attention":`#6c4801`,"status-done":`#026b49`,"status-running":`#01525f`,"status-muted":`#56637a`,tint:`11%`,agent:`#6f45c0`,meter:`#8a97ab`,"tok-input":`#4d4cc8`,"tok-cache-read":`#cdd6e3`,"tok-cache-write":`#7d8aa0`,"tok-output":`#a07ad9`,"code-keyword":`#6f49a8`,"code-string":`#076b40`,"code-number":`#7b5605`,"code-constant":`#964605`,"code-comment":`#5d6b80`,"code-function":`#086586`,"code-type":`#785902`,"code-name":`#095ea8`}},"github-dark":{label:`GitHub Dark`,scheme:`dark`,tokens:{backdrop:`#010409`,bg:`#010409`,card:`#0d1117`,panel:`#0d1117`,panel2:`#151b23`,raise:`#212830`,well:`#010409`,track:`#262c36`,line:`#262c36`,line2:`#3d444d`,shadow:`#010409`,text:`#f0f6fc`,"text-2":`#d1d7e0`,"text-muted":`#9299a2`,accent:`#4796fb`,focus:`#1f6feb`,"focus-width":`2px`,selection:`#388bfd4d`,"status-failed":`#fc554d`,"status-attention":`#d29922`,"status-done":`#3fb950`,"status-running":`#39c5cf`,"status-muted":`#9198a1`,tint:`15%`,agent:`#ab7df8`,meter:`#656c76`,"tok-input":`#58a6ff`,"tok-cache-read":`#2f3742`,"tok-cache-write":`#656c76`,"tok-output":`#d2a8ff`,"code-keyword":`#ff7b72`,"code-string":`#a5d6ff`,"code-number":`#79c0ff`,"code-constant":`#79c0ff`,"code-comment":`#9198a1`,"code-function":`#d2a8ff`,"code-type":`#ffa657`,"code-name":`#7ee787`}},"github-light":{label:`GitHub Light`,scheme:`light`,tokens:{backdrop:`#f6f8fa`,bg:`#f6f8fa`,card:`#ffffff`,panel:`#ffffff`,panel2:`#ffffff`,raise:`#eff2f5`,well:`#f6f8fa`,track:`#e6eaef`,line:`#d1d9e0`,line2:`#b7c0ca`,shadow:`#1f232833`,text:`#1f2328`,"text-2":`#393f46`,"text-muted":`#59636e`,accent:`#0165d6`,focus:`#0165d6`,"focus-width":`2px`,selection:`#0969da33`,"status-failed":`#cd1e2b`,"status-attention":`#916103`,"status-done":`#147b33`,"status-running":`#10767d`,"status-muted":`#59636e`,tint:`8%`,agent:`#804ddc`,meter:`#818b98`,"tok-input":`#54aeff`,"tok-cache-read":`#d1d9e0`,"tok-cache-write":`#818b98`,"tok-output":`#a475f9`,"code-keyword":`#cf222e`,"code-string":`#0a3069`,"code-number":`#0550ae`,"code-constant":`#0550ae`,"code-comment":`#59636e`,"code-function":`#6639ba`,"code-type":`#953800`,"code-name":`#116329`}},"one-dark":{label:`One Dark`,scheme:`dark`,tokens:{backdrop:`#21252b`,bg:`#21252b`,card:`#282c34`,panel:`#282c34`,panel2:`#2c313a`,raise:`#2c313a`,well:`#21252b`,track:`#3a3f4b`,line:`#181a1f`,line2:`#4b5263`,shadow:`#0e1013`,text:`#d7dae0`,"text-2":`#abb2bf`,"text-muted":`#a7afbe`,accent:`#64b2f2`,focus:`#528bff`,"focus-width":`2px`,selection:`#3e4451`,"status-failed":`#fc858d`,"status-attention":`#e5c07b`,"status-done":`#98c379`,"status-running":`#57b7c3`,"status-muted":`#a7afbe`,tint:`12%`,agent:`#d788ee`,meter:`#5c6370`,"tok-input":`#61afef`,"tok-cache-read":`#3e4451`,"tok-cache-write":`#5c6370`,"tok-output":`#c678dd`,"code-keyword":`#c678dd`,"code-string":`#98c379`,"code-number":`#d19a66`,"code-constant":`#d19a66`,"code-comment":`#8f949e`,"code-function":`#61afef`,"code-type":`#e5c07b`,"code-name":`#e36e77`}},nord:{label:`Nord`,scheme:`dark`,tokens:{backdrop:`#2e3440`,bg:`#242933`,card:`#2e3440`,panel:`#2e3440`,panel2:`#323946`,raise:`#3b4252`,well:`#272c36`,track:`#3b4252`,line:`#3b4252`,line2:`#4c566a`,shadow:`#1d2129`,text:`#eceff4`,"text-2":`#d8dee9`,"text-muted":`#adbcd9`,accent:`#9dbedf`,focus:`#88c0d0`,"focus-width":`2px`,selection:`#4c566a`,"status-failed":`#fe9aa1`,"status-attention":`#ebcb8b`,"status-done":`#a5c18e`,"status-running":`#89c1d1`,"status-muted":`#adbcd9`,tint:`13%`,agent:`#d0a9c9`,meter:`#7b88a1`,"tok-input":`#5e81ac`,"tok-cache-read":`#4c566a`,"tok-cache-write":`#7b88a1`,"tok-output":`#b48ead`,"code-keyword":`#81a1c1`,"code-string":`#a3be8c`,"code-number":`#b790b0`,"code-constant":`#d38972`,"code-comment":`#8f9db8`,"code-function":`#88c0d0`,"code-type":`#8fbcbb`,"code-name":`#8fbcbb`}},"high-contrast":{label:`High contrast`,scheme:`dark`,tokens:{backdrop:`#010409`,bg:`#010409`,card:`#0a0c10`,panel:`#0a0c10`,panel2:`#0a0c10`,raise:`#1c2128`,well:`#010409`,track:`#272b33`,line:`#7a828e`,line2:`#9ea7b3`,shadow:`#000000`,text:`#ffffff`,"text-2":`#f0f3f6`,"text-muted":`#bdc4cc`,accent:`#7abbfe`,focus:`#7abbfe`,"focus-width":`3px`,selection:`#409eff66`,"status-failed":`#ffacb8`,"status-attention":`#fad209`,"status-done":`#0ef38e`,"status-running":`#62ceff`,"status-muted":`#bdc4cc`,tint:`12%`,agent:`#c299fe`,meter:`#9ea7b3`,"tok-input":`#409eff`,"tok-cache-read":`#525964`,"tok-cache-write":`#9ea7b3`,"tok-output":`#dbb7ff`,"code-keyword":`#ff9492`,"code-string":`#addcff`,"code-number":`#91cbff`,"code-constant":`#91cbff`,"code-comment":`#bdc4cc`,"code-function":`#dbb7ff`,"code-type":`#ffb757`,"code-name":`#72f088`}}},qe=e=>`--ca-theme-${e}`;function Je(e){return Be.map(t=>{let n=Ke[t],r=Object.entries(n.tokens).map(([e,t])=>`${qe(e)}: ${t};`);return`${e(t)} { color-scheme: ${n.scheme}; ${qe(`color-scheme`)}: ${n.scheme}; ${r.join(` `)} }`}).join(`
`)}var Ye=e=>Be.includes(e),Xe=e=>Ve.includes(e);function Ze(e,t){return e===`system`?t?We.light:We.dark:Ye(e)?e:Ue}var Qe=`contraagent:theme`,$e=()=>{try{return globalThis.localStorage}catch{return}};function et(e=$e()){try{let t=e?.getItem(Qe);if(Xe(t))return t}catch{}return Ue}function tt(e,t=$e()){try{t?.setItem(Qe,e)}catch{}}var nt=()=>globalThis.matchMedia?.(`(prefers-color-scheme: light)`).matches??!1;`${JSON.stringify(Qe)}${JSON.stringify(Be)}${JSON.stringify(Ve)}${JSON.stringify(Ue)}${JSON.stringify(We.light)}${JSON.stringify(We.dark)}`;var rt=s(Je(e=>`[data-ca-theme="${e}"]`)),it=s(Je(e=>`:host([data-ca-theme="${e}"])`)),at=new WeakSet;function ot(e=document){if(at.has(e))return;let t=rt.styleSheet;t&&`adoptedStyleSheets`in e&&(e.adoptedStyleSheets=[...e.adoptedStyleSheets,t],at.add(e))}function j(e,t,n){e.dispatchEvent(new CustomEvent(t,{detail:n,bubbles:!0,composed:!0}))}var st=[`overview`,`tasks`,`journal`,`outputs`,`definitions`,`procs`,`stream`],ct=[`transcript`,`input`,`output`,`definition`],lt=e=>st.includes(e)||/^panel:.+/.test(e),ut=e=>ct.includes(e);function dt(e){let t=new URLSearchParams(e),n=t.get(`tab`)??``,r=t.get(`view`)??``,i=Number(t.get(`round`));return{run:t.get(`run`)??``,tab:lt(n)?n:`overview`,key:t.get(`key`)||null,view:ut(r)?r:`transcript`,round:Number.isInteger(i)&&i>0?i:null,def:t.get(`def`)||null,kind:t.get(`kind`)??``,stop:t.get(`stop`)??``,q:t.get(`q`)??``,layer:t.get(`layer`)??``,unit:t.get(`unit`)??``,sel:t.get(`sel`)??``}}function ft(e){let t=new URLSearchParams;e.run&&t.set(`run`,e.run),e.tab!==`overview`&&t.set(`tab`,e.tab),e.tab===`stream`&&(e.key&&t.set(`key`,e.key),e.view!==`transcript`&&t.set(`view`,e.view),e.round!=null&&t.set(`round`,String(e.round))),e.tab===`definitions`&&e.def&&t.set(`def`,e.def),e.tab===`overview`&&e.layer&&t.set(`layer`,e.layer),e.tab===`overview`&&e.unit&&t.set(`unit`,e.unit),e.tab===`overview`&&e.sel&&t.set(`sel`,e.sel);let n=e.tab===`tasks`||e.tab===`journal`;n&&e.kind&&t.set(`kind`,e.kind),e.tab===`journal`&&e.stop&&t.set(`stop`,e.stop),n&&e.q&&t.set(`q`,e.q);let r=t.toString();return r?`?${r}`:``}function pt(e,t){let n={...e,...t};return t.run!==void 0&&t.run!==e.run&&Object.assign(n,{key:null,def:null,round:null,layer:``,unit:``,sel:``,...t}),t.layer!==void 0&&t.layer!==e.layer&&t.sel===void 0&&(n.sel=``),t.key!==void 0&&t.key!==e.key&&(t.view===void 0&&(n.view=`transcript`),t.round===void 0&&(n.round=null)),n}function mt(e,t){let n=e=>ft({...e,kind:``,stop:``,q:``,unit:``,sel:``});return n(e)!==n(t)}var ht=`contraagent`,gt=200,_t=null,vt=``,yt=null;function bt(){let e=globalThis.history?.state;return e&&typeof e==`object`?e:{}}function xt(){let e=bt()[ht];return e&&typeof e==`object`?e:{}}function St(){let e=xt().entry;if(e)return e;let t=Math.random().toString(36).slice(2);return history.replaceState({...bt(),[ht]:{...xt(),entry:t}},``),t}function Ct(){yt&&clearTimeout(yt),yt=null;let e=_t;_t=null,e&&globalThis.history&&xt().entry===vt&&history.replaceState({...bt(),[ht]:{...xt(),...e}},``)}function wt(e){if(globalThis.history)return _t&&vt===xt().entry&&e in _t?_t[e]:xt()[e]}function Tt(e,t){if(!globalThis.history)return;let n=St();_t&&vt!==n&&(_t=null),vt=n,(_t??={})[e]=t,yt??=setTimeout(Ct,gt)}function Et(){Ct()}globalThis.addEventListener?.(`pagehide`,Et);var Dt=class{constructor(e){this.id=e,this.items=new Set(wt(e)??[])}has(e){return this.items.has(e)}set(e,t){t!==this.items.has(e)&&(t?this.items.add(e):this.items.delete(e),Tt(this.id,[...this.items]))}},Ot=class{constructor(e){this.id=e;let t=null;try{t=JSON.parse(globalThis.sessionStorage?.getItem(`${ht}:${e}`)??`null`)}catch{}this.items=new Set(Array.isArray(t)?t.filter(e=>typeof e==`string`):[])}has(e){return this.items.has(e)}set(e,t){if(t!==this.items.has(e)){t?this.items.add(e):this.items.delete(e);try{globalThis.sessionStorage?.setItem(`${ht}:${this.id}`,JSON.stringify([...this.items]))}catch{}}}},kt=class{constructor(e,t,n){this.mode=e,this.onChange=t,this.onPop=()=>{this.current=dt(location.search),this.onChange(this.current,`pop`)};let r=dt(e===`url`?location.search:``);this.current=pt(r,n??{})}get route(){return this.current}start(){this.mode===`url`&&(history.scrollRestoration=`manual`,addEventListener(`popstate`,this.onPop)),this.onChange(this.current,`init`)}stop(){this.mode===`url`&&removeEventListener(`popstate`,this.onPop)}navigate(e,t={}){let n=pt(this.current,e);if(ft(n)===ft(this.current))return;let r=!t.replace&&mt(this.current,n);if(this.current=n,this.mode===`url`){let e=`${location.pathname}${ft(n)}${location.hash}`;r?(Et(),history.pushState({},``,e)):history.replaceState(history.state,``,e)}this.onChange(n,r?`push`:`replace`)}},At=`lit-localize-status`,M=(e,...t)=>({strTag:!0,strings:e,values:t}),jt=e=>typeof e!=`string`&&`strTag`in e,Mt=(e,t,n)=>{let r=e[0];for(let i=1;i<e.length;i++)r+=t[n?n[i-1]:i-1],r+=e[i];return r},Nt=(e=>jt(e)?Mt(e.strings,e.values):e),N=Nt,Pt=!1;function Ft(e){if(Pt)throw Error(`lit-localize can only be configured once`);N=e,Pt=!0}var It=class{constructor(e){this.__litLocalizeEventHandler=e=>{e.detail.status===`ready`&&this.host.requestUpdate()},this.host=e}hostConnected(){window.addEventListener(At,this.__litLocalizeEventHandler)}hostDisconnected(){window.removeEventListener(At,this.__litLocalizeEventHandler)}},Lt=e=>e.addController(new It(e)),P=()=>(e,t)=>(e.addInitializer(Lt),e),Rt=class{constructor(){this.settled=!1,this.promise=new Promise((e,t)=>{this._resolve=e,this._reject=t})}resolve(e){this.settled=!0,this._resolve(e)}reject(e){this.settled=!0,this._reject(e)}},zt=[];for(let e=0;e<256;e++)zt[e]=(e>>4&15).toString(16)+(e&15).toString(16);function Bt(e){let t=0,n=8997,r=0,i=33826,a=0,o=40164,s=0,c=52210;for(let l=0;l<e.length;l++)n^=e.charCodeAt(l),t=n*435,r=i*435,a=o*435,s=c*435,a+=n<<8,s+=i<<8,r+=t>>>16,n=t&65535,a+=r>>>16,i=r&65535,c=s+(a>>>16)&65535,o=a&65535;return zt[c>>8]+zt[c&255]+zt[o>>8]+zt[o&255]+zt[i>>8]+zt[i&255]+zt[n>>8]+zt[n&255]}var Vt=`h`,Ht=`s`;function Ut(e,t){return(t?Vt:Ht)+Bt(typeof e==`string`?e:e.join(``))}var Wt=new WeakMap,Gt=new Map;function Kt(e,t,n){if(e){let r=e[n?.id??qt(t)];if(r){if(typeof r==`string`)return r;if(`strTag`in r)return Mt(r.strings,t.values,r.values);{let e=Wt.get(r);return e===void 0&&(e=r.values,Wt.set(r,e)),{...r,values:e.map(e=>t.values[e])}}}}return Nt(t)}function qt(e){let t=typeof e==`string`?e:e.strings,n=Gt.get(t);return n===void 0&&(n=Ut(t,typeof e!=`string`&&!(`strTag`in e)),Gt.set(t,n)),n}function Jt(e){window.dispatchEvent(new CustomEvent(At,{detail:e}))}var Yt=``,Xt,Zt,Qt,$t,en,tn=new Rt;tn.resolve();var nn=0,rn=e=>(Ft(((e,t)=>Kt(en,e,t))),Yt=Zt=e.sourceLocale,Qt=new Set(e.targetLocales),Qt.add(e.sourceLocale),$t=e.loadLocale,{getLocale:an,setLocale:on}),an=()=>Yt,on=e=>{if(e===(Xt??Yt))return tn.promise;if(!Qt||!$t)throw Error(`Internal error`);if(!Qt.has(e))throw Error(`Invalid locale code`);nn++;let t=nn;return Xt=e,tn.settled&&(tn=new Rt),Jt({status:`loading`,loadingLocale:e}),(e===Zt?Promise.resolve({templates:void 0}):$t(e)).then(n=>{nn===t&&(Yt=e,Xt=void 0,en=n.templates,Jt({status:`ready`,readyLocale:e}),tn.resolve())},n=>{nn===t&&(Jt({status:`error`,errorLocale:e,errorMessage:n.toString()}),tn.reject(n))}),tn.promise},sn=`en`,cn=[`ja`],ln=[`en`,`ja`],un=t({templates:()=>dn}),dn={h5665d16ae525ca0b:O`${0} の出力`,h612ee972e5585763:O`JSON オブジェクト（スキーマ ${0}）`,h8e239826489c9dd4:O`この実行には階層 <code>${0}</code> がありません`,had57861b5eb1998e:O`ファイルなし | Python コードで定義（<code>TaskAdapter</code>）`,hf139a496c0f9b763:O`${0} の出力から`,"no-runs-yet":`実行はまだありません`,s02044ab83f193b3b:`レート制限、エラー、タイムアウトなどで失敗した後の、次のモデルへの切り替え（Router のホップ）`,s030b3188c7fcf26d:M`カスタムビュー ${0} はありません`,s0379fc73608ab971:`完了`,s0382d73823585617:M`${0}: ${1}`,s038b2a0deba58916:`ページ`,s03b454fb08e876ad:`タブ`,s03ee3cfb0919c62c:`タスク`,s03fb84d070eb4d43:M`古い試行 ${0} 件は非表示`,s051e95917479e3a4:`実行中のエージェントのセッション`,s05548eaadd7b3e53:`選択中の項目`,s061a40d8b1403d96:`OutputContract`,s0622a6e6cb77254b:`トランスクリプト`,s0668067982f84dcb:`ユニットごとのステージとステップ（CursorStore）`,s066d70cf9d5e2915:`出力`,s06a59d9f860b0c38:`Esc: 1 つ上の階層`,s06ac9901d5ec124e:`依存先`,s06bab80ab006c3bc:`エージェントのセッション開始時に報告された値です。アカウント全体の値で、同時に実行中のタスクすべてに共通です。`,s07760df6abc2f6a0:`テキストフィルター（/）`,s0799e2b0ce300ca7:M`キャッシュ ${0}`,s07da69ddbc0d4c69:`関数`,s07e46807b4a9183c:M`+${0}`,s087d6f07b52b30ec:M`${0}%`,s08b35907b5589afa:`いいえ`,s09323b2ac0a8afed:`出力の検証: OK`,s09bb59cd137c1af4:`プロンプトなし`,s0b237aba4a56eb22:`エージェントのセッション開始時のサブスクリプション利用率（アカウント全体）`,s0b355fde970b0df9:`OK`,s0b7f9dcca2fb294a:`実行前からあるファイル`,s0cf77430f4bd7c5c:M`モデル切り替えのあったタスク ${0} 件`,s0d7aa7237dcb1b28:M`キャッシュ書き込み ${0}`,s0dbd76eb398aa733:`未実行（入力ファイルの不足または検証エラー）`,s0e6bbd9fe1101fbd:`問題`,s0ea064cda0585ae9:`プラグインディレクトリ`,s0f04e0aca045fbe9:`一部省略`,s0f136ff2c086b760:`リセット済み`,s0f8b4a05ed3a104d:M`出力ファイル ${0} 件`,s10337c73438593bc:`再開カーソル`,s1072ae09dfd51f53:`種別の最初のタスクの開始時に記録（definitions/&lt;kind&gt;.json）`,s1147e23008e266b7:M`${0} 型の JSON 値`,s115763f2236ae9b6:`過去 24 時間`,s1198336b172c6e1a:`モデル切り替えのあったタスク 1 件`,s123b7254b44dd148:`待機中`,s125a86b2f45bbb25:M`要素 ${0} 個`,s12c35dcdc5890192:`型の不一致`,s14bd607323778cb3:`コーディングエージェントが報告した値`,s150f53f8651b4384:`出力`,s156d30b96fb26c7f:`なし（任意）`,s158eba9bc2227ce3:M`週の利用率 ${0}`,s1633e83dc53b5d08:`検証対象のファイルなし`,s168ae294e3e72ce4:`検証のタイミング`,s1703f5cfa8ed0cc9:M`実行されず ${0} 件`,s179ba9809bdf35c7:`アカウントごと、最初の値 → 最後の値`,s17ee023c53dcd83c:`書き込み待ち（タスクが待機中）`,s18d4d02c2e47cf0f:M`ループ内の ${0}`,s19ed92a422ad7e4c:`上限: max_concurrent`,s1a20210c3f1e40c9:M`スキップ ${0} 件`,s1a3bf4da26280428:`種別 · ユニット`,s1ac8c23d19212c8a:`エディタのテーマ`,s1acc85c236fed879:`書き込まれていない出力 1 件（タスクが未実行）`,s1b5c88ed6d70d50e:M`タスクは ${0} 回目で完了`,s1bb7c4234aa7d213:`すべてのタスクが開始済み`,s1bf54dcd1c885a20:`実行中のプロセスなし`,s1c0f7e3a9a6bce79:`パラメータ`,s1c2af4de03b03b48:`タスクが選択されていません`,s1c4244f27dc0a0ad:M`セッション開始時の利用率（アカウント全体）: ${0}`,s1c76dcdfd0d3326d:`実行に登録されたすべてのタスク（種別ごと、plan.jsonl）`,s1cc744978f1e1e36:`実行中の Python タスク`,s1db2936d905dfc71:`API エラー`,s1dc338639fe7aae9:M`試行 ${0} 回`,s1dd7ab260efc97bf:`実行中のタスクなし`,s1e9a9d076c64051d:M`プロンプト（${0} 文字、ほか ${1} 文字は未保存）`,s1ebbae8f5810b65b:`入力`,s1f53dce0721a5fdc:M`所要時間 ${0}`,s2073c04640f9ffe1:`修正依頼: 検証エラー後の、同じエージェントのセッション`,s20e04bdc808a6442:M`リセットまで ${0}`,s217ae8afd4252eff:`あり`,s2216c1ec1d2b68a8:`JSON ではありません`,s224181db56bd4f90:`ツール実行中に中止`,s229e98b8f3010c9f:M`修正依頼 ${0} 回で完了。最初の検証エラー: ${1}`,s22d4df747c023383:M`修正依頼 1 回で完了。最初の検証エラー: ${0}`,s23005b43f30a04ed:`スキーマにないフィールド`,s234af65b52814aa0:`終了した試行はまだありません`,s236ae937cbcd6a39:`拡大`,s23ba00b0f333e17e:M`${0} 回の試行がすべて失敗: ${1}`,s23f40d3ffdd352a6:`定義はまだありません`,s2575361362fcf642:`OutputContract・InputContract を宣言したタスクはありません`,s26012de2ae38a284:`API 呼び出し 1 回`,s26bae2d058ab07f8:`ユニットなし`,s26bb7d0992115fe1:`実行した試行の回数（リトライを含む、journal.jsonl）`,s26e1e2905dce8250:M`API 呼び出し ${0} 回`,s27bbde3f68fad181:M`ユニット: ${0}`,s28f91da403800c05:`InputContract`,s2a2e8a5afcc8d89a:`現在`,s2ac18b95949a85cb:M`${0}: ${1}、次のモデルに切り替え`,s2b82c03a0f482d56:`入力ファイルの不足または検証エラー`,s2cf203a7f1d1b7cb:`修正依頼: 出力が検証エラーになった後の、同じエージェントのセッションでの次のラウンド`,s2dd7dfcce562730a:`試行の結果（stop）`,s2e3f7c747d87ba60:M`ほかの出力 ${0} 件`,s2e422519ed38f7d8:`周`,s2ec303c39937657c:`タスクは実行中`,s2f3435308f48080e:M`${0} 周`,s2f3c9db4daa3e192:`問題なし`,s2f4e0fd086ad4b96:`すべての出力`,s2f54740b39931f87:`定義なし`,s2faec8a0d7db08dd:M`5 時間枠の利用率 ${0}（リセット ${1}）`,s2fe3f0ef38a252c7:`ツール`,s2fea0e9e542e5b47:M`修正依頼 ${0}`,s321b04e2b2f863d5:`余分なフィールド`,s326385425f7ff3c5:M`キャッシュ読み込み ${0}`,s337a1e9022a8d19f:`表`,s33b572e03cbb49a2:`パイプラインの階層`,s343dead26eec35c9:`新しいイベント 1 件を表示`,s34970ae2312009f5:`エラーの内容は修正依頼のプロンプトに記載`,s351d1cb40ce52b1e:`終了した試行なし`,s352069454f38346a:`ファイル全体`,s355f4ca5b99c3871:`入力ファイルに検証エラー`,s367d079d1aed1358:`料金`,s36eb49cc97df66bc:M`所要時間 ${0}`,s3700ce266079b566:`Web 検索 1 回`,s370bd0b51ee4fda0:M`報告時刻 ${0}`,s37da018e1fe6a0d7:`スキーマ以外の検証（validators）`,s387a4a41718122cb:M`検索結果 ${0} 件`,s3904df152788b23c:`JSON オブジェクトではありません`,s39ee2f1fc48e6bc3:`パイプライン`,s3aa67b8233b5ecd0:`出力ファイルなし`,s3afd657caafb54ce:`上段は入力 / 出力トークン、下段はキャッシュ読み込み / キャッシュ書き込み`,s3b32dd23d086c992:`プロセスツリー`,s3bde79a5267baa21:M`task_detail コールバックが失敗: ${0}`,s3c0d17bad169557b:`なし`,s3c6c1ae328e812d5:`実行した試行の回数`,s3cd8af104999d502:`実行中のエージェントのセッション 1 件`,s3d03990e188bfbff:`エージェントのセッション`,s3d197283cb019b5a:`概要`,s3d99e317c3b7b422:`検証エラー後の、同じエージェントのセッション`,s3d9b2f1277134dfc:`テキストファイル`,s3f18b1a78ce1a960:`各タスクが書き込むファイル`,s3f6e4868742b58de:M`${0} 回目で完了（失敗 ${1} 回）。最初の失敗: ${2}`,s3f7074a6bbbd7726:`修正依頼`,s3fd6bd99e3f6a5be:`開始`,s40750d44c5ea3271:M`${0}: 入力`,s4085b471de2e2215:`週の利用率`,s4134711b0b981089:`Tab: 次のノード`,s4156c144093d2565:`修正依頼が 1 回以上あった試行`,s423b98420bc4f51a:M`${0} 回目で完了（失敗 1 回）。最初の失敗: ${1}`,s42a1ebe17efda727:`フィールド`,s42c16f17debe21c7:M`${0} ステップ完了`,s42cbd8dca939a9c7:`検証`,s43809cc80b3f099a:`ハイライトを解除`,s43ab3e3c4dea42fc:`入力ファイル`,s448ad430047b3ff5:`ファイルの検証: OK`,s451bb7dd42aaf221:`料金の高いタスク`,s454c0dcbb0dffc2f:M`${0} のループの各周`,s45de7528c20a0792:M`${0}（カスタムビュー）`,s467ceab5071e77a3:M`1 周: ${0}`,s46f1d86ffec6223c:`エラーで終了`,s473bad4c26a1a663:`キャッシュ読み込み`,s478b912874fef59f:`検証対象のファイル（OutputContract、InputContract）`,s47a6fad95948980d:M`このタスクの入力 ${0} 件`,s47b9912260b01c3c:`Python タスク`,s47c42ef44972974f:`未対応のイベント`,s48287bbcb6ba7b8d:M`終了 ${0}`,s48e186fb300e5464:`所要時間`,s49098dfd8a30a9b7:`モニターのサーバーに接続済み`,s491765412b82838e:M`${0} のループ`,s4abcddbf0c24a4e2:M`${0} 日前`,s4d613d768e2faa0d:`検索結果 1 件`,s4d890c06c9c42dee:`モデル切り替え`,s4efee5b48a4593cb:`ループ`,s4f0af1e75e3f4e0d:`スキーマにない`,s4fed3c544c5791df:`エージェントタスク`,s500fd71a4232050e:`空`,s521a16a18cfbcf5a:`1 ユニット`,s52c75c50315f2111:`次の周`,s52cfd5bdf53cbac3:`カスタムビュー`,s53c57cf5a0992de1:M`${0}: 未実行`,s54393bfa280ea55b:`プロンプト`,s552240946fb80e49:M`フロー呼び出し ${0}`,s5552cf25dfb16715:`プラグインディレクトリ`,s558d71789938dd8d:`認証情報の不一致`,s55fa598b754cc3cc:M`${0}（${1}）`,s5667ab3a2fddedf6:M`（ほか ${0} 文字は未保存）`,s56838581fa8422a5:M`後続タスク: ${0}`,s571b714236b36ed9:M`入力 ${0} がありません（${1} が未実行）`,s57402fcb8174003c:M`キャッシュ書き込み ${0}`,s585632ad63b34266:M`入力 ${0} がありません（${1} が失敗）`,s58c754018ec47b5f:`実行履歴`,s594159521842aa08:M`修正依頼 ${0} 回`,s59e4f00624df1f3f:`上限に接近`,s5ab755785f15d57e:`並び順`,s5b2aca393ddc3642:`修正依頼のあったタスク 1 件`,s5b91c14a6a040e1e:`種別ごとのトークンと料金`,s5cd51fca94ab558d:M`エージェントのセッション ${0} 回`,s5de9d2dc62f214f9:`依存先タスク`,s5e30a7b87ccdc74f:`書き込みなし（タスクが未実行）`,s5e6c4b6767bd9690:`テキスト（JSON 文字列）`,s5f22ded7520dee36:`ロールなし`,s5f31efe25292c85d:`エージェント・モデル・認証情報`,s5f343a43e7ea9f91:`エラー`,s5f43af3669b1e098:`ソース`,s5f7e595afb1d20c1:`なし（必須）`,s5ff154de087b8fbf:`エージェントタスク`,s60147fb4fa4a8e0c:`実行中`,s605757aea05668c5:M`未実行の後続タスク ${0} 件`,s62035be5de828c62:`キャッシュ書き込み`,s629576c6b305d539:`任意`,s630a7291de06d7e3:`実行履歴の未実行のタスク`,s6338c9c6cf8d4720:`入力・出力トークン（全試行）`,s649816288746372b:`後続タスク`,s65ca38fd016064d1:`中断`,s6645c79330d551d1:`拡大（Ctrl + スクロール）`,s6647f4305129ff48:`ファイルなし`,s664bf0dfe5ccdd70:`ツール呼び出しが戻る前に実行が終了`,s670ef751f29dc9ae:M`${0} ユニット`,s680fc90489553ed6:`タイムライン`,s68818ff23f9c3cd6:`その他の検証`,s69522c8fd29e217c:`修正依頼 1 回`,s69990579b19fd554:M`スキーマ ${0}`,s6a8fac496ab75484:M`入力 ${0} がありません（${1} が未完了）`,s6aabc9569e449784:`未実行（入力ファイルなし）`,s6b8a04c7fc4c0cfd:M`同時実行 ${0}/${1}`,s6b94519d3d694140:`タスクなし`,s6c306ba2a3eafe04:`依存先タスクなし`,s6c80deca380c99b3:`タスクなし`,s6c86e2a18e78587f:M`依存先タスク ${0} が失敗`,s6d36170fcecb00d0:`依存先タスク`,s6d739294ba8eba32:M`${1} タスク中 ${0} 件完了`,s6dbe9cb1faacdff3:M`${0} 文字`,s6ebc9bd6feae62a3:`読み込み中…`,s6f145ecab7e01aae:`API 呼び出し`,s6f2d39e45dc290b5:`出力ファイル 1 件`,s6f6ef83186f41f9c:`すべてのエージェントのセッションの合計（同時実行の分も含む）`,s6fa4fa0db6637ca7:`フロー呼び出しがエラーで終了`,s706837052444dc71:`実行グループ`,s7081cf6429d6e736:M`ループ ${0} 周目`,s70a75a654c87e121:M`タスク終了後の利用率: ${0}`,s70af97de3ad8fb23:`種別`,s71900089efd0b3f6:M`モデル切り替え: ${0}`,s7233e6b5b69a2313:`古い試行 1 件は非表示`,s7239ff29fb5724bc:M`修正依頼のあったタスク ${0} 件`,s72dc3c241ce33d1c:`ユニットごとの周回数`,s72dd85d5a32d1dc3:`キャッシュ読み込み`,s737a2225351a2d83:`ループの周回数`,s73d2ca96ea1a1a1f:`未実行の後続タスク 1 件`,s755ec54babc00670:M`プラグイン ${0}`,s75834d577f713a10:`エージェントのセッションなし`,s75ee52426b34dd6d:`実行を検索`,s7671567ef7075153:M`${0} モニター`,s769a35c122b0add4:M`${0}: ${1}、${2} に切り替え`,s77ec32fb8248c021:M`未実行 ${0} 件`,s78fd8c03f8c967f3:`トークン`,s79a4abd140c07a19:M`未対応のイベント: ${0}`,s79faeb77f29174c8:M`5 時間枠の利用率 ${0}`,s7a14301773287a5c:`エラーで終了したフロー呼び出し 1 件`,s7a30a0774744040b:`出力ファイル`,s7a4c9d94aaf75c45:`権限エラー`,s7ae3a2df31f642c2:`試行が 2 回以上のタスク`,s7ae683e966f797d8:`タスクは待機中`,s7b16665b242b03f9:`入力ファイルなし`,s7b1cef9707986270:`修正依頼のあった試行`,s7c08c2107990421e:M`${0} を表示`,s7c95876637f6a9d7:`フィルター`,s7ccddac9af610a9c:M`${0} 回目で完了（失敗 1 回）`,s7cd807ec1a76a454:`このタスクの入力 1 件`,s7cfd548e0b7e3ad7:`出力が止まった`,s7e796fe83982863f:M`ロール ${0}`,s7f59f507e02a2f38:`表示形式`,s7ff1975047cd672c:`コーディングエージェントが使ったモデル`,s803ce7e1a2294d50:`ファイル`,s8162d2730a5efc31:`モデル切り替えなし`,s81784b8f13a711a6:`モデル切り替え: 次のモデルでの新しいエージェントのセッション`,s81816ae715e0080c:`入力ファイルの不足または検証エラーで、タスクは未実行`,s822f38a61c9dbabc:M`以前の試行のモデル: ${0}`,s837f3597be0e0bda:M`書き込み ${0}`,s83a117a0e5a969a7:`1 ステップ完了`,s84126fa92f00b4ef:`たった今`,s843c1705315bbf4e:M`修正依頼 ${0} 回後`,s84fb675fb17d4455:`リトライ`,s851220394bf4ca62:M`テーマ: ${0}`,s851d0f73d02cf0b5:`ファイルの値`,s85994a70cd39166c:`実行中`,s85e6ce57abc3c81c:M`${0}: モデル切り替え`,s863c685c886dd083:M`入力 ${0} がありません`,s864c948d4629240f:`全体を表示`,s877a8bf58317ec9e:M`${0} 回目の失敗後の、新しいエージェントのセッション`,s87aaf1391fb727b7:`実行されず`,s87b0c0d87ec9c3a1:M`モデル切り替え後に完了: ${0}`,s87cfcf0fecad5ace:`修正依頼 1 回後`,s888d98a196a240d8:`入力`,s88e6f151026426e7:M`修正依頼 ${0}`,s892f20ba2aadea33:M`入力 ${0}（${1} の出力）がありません`,s89ece7813063852e:`パラメータなし`,s8a56a8c8bd19c9c7:`なし`,s8a59bcc106a68c08:M`PID ${0}`,s8ab194afc8c3ff86:`コーディングエージェント`,s8ad90bcc234667ee:`周回数`,s8b14867a2824dc66:`リトライしたタスク`,s8bbe7f1c618318b1:`終了したすべての試行から集計（journal.jsonl）`,s8c1837e74a81ad0d:M`${0} 分前`,s8d4bb019f3bc7202:`PID`,s8dd1924ee42c1f45:M`キャッシュ読み込み ${0}`,s8de4c61438ac59f8:`再開後の実行での、新しいエージェントのセッション`,s8dfeaf9950df0ffa:`オブジェクト`,s8e337d18c39babc7:`アシスタント`,s8e609688324130a6:`Python コードで定義`,s8e92b07ba776ed4a:M`ほか ${0} アカウント`,s8eaa2ebab2c57d9f:`Tab: 次の行`,s8eec5711640b68b9:M`コーディングエージェントのイベント種別のうち、このバージョンの contraagent が対応していないもの: ${0}`,s8f18916860db5d80:`選択を解除`,s8f26e0f086cc2787:`ユニット`,s8f5f41272268128f:`未実行`,s90f3ce6dfe4ed0ce:`認証エラー`,s9147091d090a92d4:M`最大 ${0} 周`,s919d209719302bd3:M`${0}d ${1}h`,s9246c889a0392130:M`モデル ${0}`,s92a32f8361a3a3b0:M`依存先タスク ${0} 件の出力待ち`,s92b7e489ad4779c7:M`5 時間枠 ${0}`,s9340e2a9e1808cbd:`試行 1 回`,s947887a004e02e33:M`作成元: ${0}`,s94d63573d312fe9b:`認証情報`,s94f08f46277af7d6:`実行中のタスク`,s95f6abd3bc028e9c:M`依存先: ${0}`,s967a2db7049dc90e:M`失敗 ${0} 件`,s96ad55844e8c85d9:`コンテキストの上限`,s96cd46414e7cb3ee:M`出力 ${0}`,s9709015aaaed72e8:`実行中ではありません`,s97c3c9984ad4bbbc:M`修正依頼 ${0} 回で完了`,s980dd0446ac478b4:`テキストフィルター`,s98fc8cf0000154d3:`入力ファイルなし`,s9a23fee499e1a22d:`すべてのプロセス`,s9a44f95f7acf28e0:M`失敗: ${0}`,s9a629cca97d7a771:M`Web 検索 ${0} 回`,s9b1a610c6b10af9d:`実行中ではありません`,s9b7d6466c580aa00:`書き込みなし（タスクが失敗）`,s9cb681a778c29f1b:`内部の表示あり`,s9d60d7651126c205:`最終応答なしで終了`,s9de543933e6e703a:`モデル`,s9e06cbf9c5f57859:M`状態: ${0}`,s9e8afbe69b10d822:`未実行（入力ファイルに検証エラー）`,s9f0023dbc7b35c31:M`入力 ${0}`,s9f7452dd75d54d31:`エラー`,s9f92162e244d030b:M`${0} の内部`,s9f979c9a653c5aa5:`料金の上限`,s9fbbc819fe7e66aa:`実行`,s9fd13600c5948a5d:`タスクの開始前からあるファイルも有効`,s9ff6bfdb36b47dd6:`モデル切り替え`,sa0a6e71350fd953b:`出力を待つ`,sa12ff035c78855af:`コーディングエージェントが認証に使ったアカウントまたは API キー（credential）`,sa23567d1be73e6a7:`ターン数の上限`,sa335a9687e946152:`後続タスクなし`,sa358ec1ff0c833b9:`ロール`,sa35c067275510aa7:`試行`,sa390213ff60c0fd9:M`実行中のエージェントのセッションの新しいイベント ${0} 件を表示`,sa3c9339de23c1752:`形式`,sa3d3f3845c4fa2c4:M`週の利用率 ${0}（リセット ${1}）`,sa434ad4d2100f245:`作成元`,sa48318e1513f445c:`コマンドライン`,sa50a6326530d8a0d:`折りたたむ`,sa58fd816ed43f98e:`周回数`,sa6295f265bf36f55:M`${0}: トランスクリプト`,sa65ede9447b8f6f0:M`${0} 回目で完了（失敗 ${1} 回）`,sa66db52d0401c35d:M`前の ${0} 行を表示`,sa71f10bfe8f2e3b9:`期待する型`,sa74be5e915086e8e:`縮小（Ctrl + スクロール）`,sa81e2cdaf6921adc:`システム設定に合わせる`,sa84bd87e8f0df3f5:M`新しいイベント ${0} 件を表示`,sa86ea054ad5277ce:M`${0} 時間前`,sa87126e2d984d351:`ソースを表示`,sa8865b3bf47ba11f:M`${0} の入れ子のループ`,sa8bd7200899b14c8:`Shift + 矢印キー: 依存先タスク・後続タスク`,sa9ba2bef6a85be35:`タスク詳細`,saa08e9b351f629c4:`書き込み待ち（タスクが実行中）`,saa29a2ac03cd9d19:`理由`,saaaf4d8d7823ecc2:`5 時間枠の利用率`,saab875d8cfcfe712:`テーマ`,sab5bbfc5ec1101a1:M`${0} 行目`,sabd480ab5c691fa7:`思考`,sac1ead3bc64c3402:`モニターのサーバーに未接続`,sad3e3c8146fc920f:`状態`,sad951affb16c18e8:`API リクエストを再送`,sae5d87e99fe081e0:`必須`,sae675aed0baadfc5:`実行履歴のリトライしたタスク`,safdeae829048fe4f:M`${0} 回目が失敗: ${1}`,sb05ee36313adad06:`エラー`,sb067d7b999cdf867:`実行履歴の修正依頼のあった試行`,sb0c5ebf2450daf53:`サブスクリプションの利用率`,sb0fd4b074f0dc196:`Python タスク 1 回`,sb105a27af3c34dd9:M`未実行: ${0}`,sb1068f146c4596c3:`検索語`,sb1ffef0fea624d13:`前の 1 行を表示`,sb26a93fd31e2f700:`登録順`,sb26f6e41558f71ed:`表示中の階層の外`,sb271968591691cd3:`Enter: 開く`,sb289ca473d87fa82:`キャッシュ書き込み`,sb31160f9d54a1178:M`プロンプト（${0} 文字）`,sb45a9b8907f0b38a:`リトライしたタスク 1 件`,sb4d67c0a20dacf94:`トランスクリプトなし`,sb51d4fbebeb0e2ec:`パイプラインのプロセス内`,sb53f7a197981b790:`はい`,sb557a3a544242a40:`コーディングエージェントが報告した値`,sb5ae7a6b849639af:`未実行`,sb6bb16aa7550533d:`タスク実行中の書き込みが必須`,sb89b16909f010061:`エージェントのセッション 1 回`,sb9855c13b2b8461f:M`${0}: 完了`,sb998a18b54658de7:`トークンと料金`,sb9c8c7e97598bc93:M`Python タスク: ${0}`,sba376ab929e3896d:`1 周`,sba781480d2e52d6a:`ほかの出力 1 件`,sba8659178319945b:`検証を通るファイルを書き込む前に、タスクが失敗`,sbaf87689cccc53eb:`要素 1 個`,sbb202211084591ed:`開始時の利用率`,sbb77dd1d4c08e701:M`${1} タスク中 ${0} 件が未完了`,sbb99d4ec27fbb263:`終了`,sbc65d1b9648966de:M`${0} 周: ${1}`,sbc95529382a8202f:M`以前の試行のモデル: ${0}`,sbca0391cb2c7c054:`タスクの開始時`,sbcce076a4882d945:`依存先タスクが失敗`,sbce72abc083f229d:`失敗した試行の後の試行（毎回新しいエージェントのセッション、RetryingRunner）`,sbd4aeb401e751129:`実行を切り替え（r）`,sbd9a674a977ac3b7:`再開後`,sbe299a9270c76655:`実行履歴の失敗した試行`,sbed050affb1455dd:`全試行の合計`,sbf189e73c517d820:`種別のロール`,sbf299a5316967a33:`アクティビティなし`,sc032b109be3096a1:`それ以前`,sc15ad44c7902a717:`スキップ`,sc1ae48fd5a58a916:M`待機中 ${0} 件`,sc1b187568fa11c8c:M`リトライしたタスク ${0} 件`,sc46bcff777c978a4:`タイムアウト`,sc5751344f7cedf0f:M`入力 ${0} に検証エラー`,sc5b9f26a8c698f76:`次のモデルでの新しいエージェントのセッション`,sc61813a1424783fc:M`週 ${0}`,sc65ea2cf2f21a13a:`縮小`,sc6c0d07e39170334:M`書き込まれていない出力 ${0} 件（タスクが未実行）`,sc6fd207e5b80c46e:M`エラーで終了したフロー呼び出し ${0} 件`,sc797fd9076cc136d:`タスク`,sc7d1e9a9024b4f9c:`同時実行（上限）`,sc87df95c02f9306d:M`終了 ${0}`,sc92905d14a9421f3:`空き`,sca4ca1724004c913:`プロセスなし`,sca68313fa6851125:`プレビューを表示`,sca7fed2bef53cb99:`ロール`,scb862deeee160b4a:`終了（未完了のタスク 1 件）`,scb967cb2ce8bd344:`最終試行の終了時刻`,scbd3558d2cfc7dc3:`全文`,sccad21b77f9a317c:M`最も高い種別: ${0}`,sccce3de7b4abfdfe:`モデルが応答を拒否`,scd945ec17b61f103:`エージェントの所要時間`,scdb3c8f0d50a81af:`Esc: 選択を解除`,scdece4ad70d57deb:`ループ`,sce26f796a9b94ef1:`各タスクが読み込むファイル（タスクの開始時に検証）`,scf1f6260b486064d:`一致する実行なし`,scf4185bf1a2d6adf:M`完了 ${0} 件`,scf70a5a7a06e1fa5:`レート制限`,sd1f67ae2a58049b0:`ファイルの検証に使うスキーマ`,sd3c028fcc08b18ab:`登録済みのタスクなし`,sd3ec6686aaaf1324:M`終了（未完了のタスク ${0} 件）`,sd47e3a005069edb9:`ローカルの認証情報（ambient）`,sd5a8fb496330927a:`ファイルに検証エラー`,sd5da7ee4a43a6b2d:M`トークン: 入力 ${0}、出力 ${1}、キャッシュ読み込み ${2}、キャッシュ書き込み ${3}`,sd68011705bf4b72f:`プロンプトは保存されていません（keep_transcripts = false）`,sd7338946b42394f4:`失敗`,sd7445330352af2c5:`検証対象のファイル`,sd747248fb64d7bb2:`なし（任意）`,sd757815e3da2dde5:`検証エラー`,sd7768c230e48ac70:M`全体の ${0}%`,sd77d82bf43357ecd:`実行中のエージェントのセッションの新しいイベント 1 件を表示`,sd794d5178cc31502:`出力が検証エラーになった後の、同じエージェントのセッションでの追加のラウンド（rounds）`,sd798aaccd0308806:`結果を受けて作成`,sd7d77bef673bd45f:M`入力 ${0}（${1} の出力）に検証エラー`,sd8284849892c5c5a:`タスクの開始前からあるファイルは無効`,sd93128c9fde34bb6:M`依存先タスク ${0} の出力待ち`,sda249baca3c52d27:M`セッション開始時の利用率: ${0}`,sda800fa8314eb82c:M`すべて表示（${0} 文字）`,sdb1595f5c742dfbb:`入力`,sdb80a6330c0fa072:`出力に検証エラー`,sdc40078597054827:M`実行グループ ${0}`,sdc51fb6761fd6e91:`完了`,sdd0fb64c2928422f:`コーディングエージェントのイベント種別のうち、このバージョンの contraagent が対応していないもの`,sdd826d4b3e02f41b:`修正依頼なし`,sdf452c95fdeb4be0:`リトライなし`,sdf922ccc13491763:`リトライ後に完了`,se2788d18bd1f9873:`タスクを実行した CLI（claude、omp）`,se2bad0e4af9e9155:M`キー ${0} 個: ${1}`,se2cd8c3175e8f91f:M`期待する型: ${0}`,se3b4c857f91f80d7:`キーボードショートカット`,se5ad61b61dc5c4f6:`モデル切り替え`,se5d1247fe34fbb95:`monitor.Panel`,se60a4867465d5d31:`ハイコントラスト`,se61f0dc09b51fd35:`パイプラインのプロセス内の関数`,se66872955dc59191:`1 タスク`,se7102b7d5942a59c:M`${0} 回目`,se90f184c6aa3ffbb:`認証情報`,sea4f20ea1ece70a0:`定義`,sea67cb607ba79bea:`矢印キー: マーク`,sea748bf5cf6f28f3:M`${0} タスク`,sea7bdd2b70c8c2bb:`実行の一覧`,seac9afef1a00b5e8:`待機中`,sebada5168620c5fe:`既定`,sec2574ea71a53cc7:`すべての種別`,sec749d36a5ebf2a6:`コーディングエージェントが使ったエージェント定義（agents/&lt;role&gt;.md）`,secc170560fffe506:`上限に到達`,sed0a4ed4fcf1c063:`タスクごとに 1 つ（Backend.run）`,sed7bd1552ea928f8:`種別または関数`,sede9056322866918:`ステージなし`,seea0f53b4dbb2fb3:`結果`,seee13c69133b70b7:`スキップ`,sef0ce050d92c35e2:M`実行中 ${0} 件`,sef467f8fe7307be7:`グラフ`,sefcf950b3cc4fc3b:`言語`,sf113fa256db9617b:`終了時刻`,sf14df172fd566bcc:`最初のエージェントのセッション`,sf2b0c091b94a0303:`トークンの報告なし`,sf2d62a5d815803af:M`関数 ${0}`,sf2e5c0d258c9b689:`定義`,sf39e43f2714690bc:`周回数`,sf3cb3cd43bbe95c2:`ほか 1 アカウント`,sf3e2e1c7b6313910:`カスタムビュー`,sf466a6f271f0b682:M`${0} 周目`,sf4897f85932ebf42:`終了後の利用率`,sf56cc81a8429fcb0:`試行の終了後に、同じアカウントで最初に報告された値`,sf5dbf772d898f6e7:`ユニットごとではなく、実行ごとに 1 回実行されるタスク`,sf6d770c86ee5a684:`フロー呼び出し`,sf6e66e6e9a5d83ff:`トランスクリプトは保存されていません（keep_transcripts = false）`,sf7b714930ed98b54:M`不明（${0}）`,sf93c7009f950942a:`合計`,sfa04f4ef1995407e:`テキスト`,sfa6a5b4597c720bc:`フィルターに一致するタスクなし`,sfadf0e9dfc4b3030:`修正依頼 1 回で完了`,sfb65f5d860c9a106:M`実行中のエージェントのセッション ${0} 件`,sfbb1f6b888aed522:`失敗した試行`,sfc7ed987d0fe9679:`再開カーソルなし`,sfd313341ca75a38d:M`リトライ後に完了 ${0} 件`,sfd5b8cae918b42cb:M`要素 ${0} 個: ${1}`,sfd77270c3f54f664:`出力`,sfdd447bcde2c13ba:`プロセス`,sfddde3643e5505f4:`試行: 新しいエージェントのセッション`,sfde497acd6a6a561:`ファイルにない必須フィールド`,sfe771bfc3355dd51:M`${0}: 入力と出力`,sfe9c9abcded61e50:M`プロセス ${0}`,sff660af26c203189:`登録済みのタスクはまだありません`,sff6ef2732281bb26:`すべての試行が成功`,sff83af1548f682c0:M`${0} のタスク`,sffa12312d4ff4b9c:`定義なし`,sffb00562b267f0a5:`エージェントの起動に失敗`,sfff7f6b9ec291984:M`Python タスク ${0} 回`},fn={en:`English`,ja:`日本語`},pn=new Map([[`ja`,un]]),{getLocale:mn,setLocale:hn}=rn({sourceLocale:sn,targetLocales:cn,loadLocale:e=>Promise.resolve(pn.get(e))}),gn=`contraagent:locale`,_n=e=>ln.includes(e);function vn(){try{let e=globalThis.localStorage?.getItem(gn);if(_n(e))return e}catch{}for(let e of globalThis.navigator?.languages??[]){let t=e.toLowerCase().split(`-`)[0];if(_n(t))return t}return sn}async function yn(e){try{globalThis.localStorage?.setItem(gn,e)}catch{}await hn(e)}function F(e){if(e==null||Number.isNaN(e))return`—`;let t=Math.max(0,e);if(t<.05)return`<0.1s`;if(t<9.95)return`${t.toFixed(1)}s`;let n=Math.round(t);return n<60?`${n}s`:n<3600?`${Math.floor(n/60)}m ${String(n%60).padStart(2,`0`)}s`:`${Math.floor(n/3600)}h ${String(Math.floor(n%3600/60)).padStart(2,`0`)}m`}var bn=new Map;function xn(e,t){let n=`${e}|${t}`,r=bn.get(n);return r||(r=new Intl.DateTimeFormat(e,{...t?{month:`short`,day:`numeric`}:{},hour:`2-digit`,minute:`2-digit`,second:`2-digit`,hourCycle:`h23`}),bn.set(n,r)),r}function Sn(e,t=!1,n=mn()){if(!e)return``;let r=new Date(e);return Number.isNaN(r.getTime())?e:xn(n,t).format(r)}function Cn(e,t=Date.now()){let n=Date.parse(e||``);if(Number.isNaN(n))return``;let r=Math.max(0,(t-n)/1e3);return N(r<60?`just now`:r<3600?M`${Math.floor(r/60)}m ago`:r<86400?M`${Math.floor(r/3600)}h ago`:M`${Math.floor(r/86400)}d ago`)}var wn=e=>e.charAt(0).toLocaleUpperCase(mn())+e.slice(1),I=(...e)=>e.filter(Boolean).join(` | `),L=(e,t=` · `)=>`${e.kind??``}${e.unit?t+e.unit:``}`;function Tn(e){let t=(e||``).trim();if(!t)return``;let n=(t.split(`
`)[0]||``).trim();return n.length>100?`${n.slice(0,100)}…`:n}var R=e=>String(e??``).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`);function z(e){let t=e??0;return t<1e3?String(Math.round(t)):t<1e4?`${(t/1e3).toFixed(1).replace(/\.0$/,``)}k`:t<1e6?`${Math.round(t/1e3)}k`:`${(t/1e6).toFixed(1).replace(/\.0$/,``)}M`}function En(e){return e==null?`—`:e===0?`$0`:e<.001?`<$0.001`:e<1?`$${e.toFixed(3)}`:`$${e.toFixed(2)}`}function Dn(e){let t=new Map;for(let n of e)for(let[e,r]of Object.entries(n.unread_events??{}))t.set(e,(t.get(e)??0)+r);return[...t].map(([e,t])=>`${e} ×${t}`).join(`, `)}var On=new Set(`and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield`.split(` `)),kn=new Set([`None`,`True`,`False`,`self`,`cls`]),An=new Set(`str int float bool list dict set tuple bytes object type len range print isinstance super Optional Literal Any Union Path`.split(` `)),jn=new RegExp([`(#[^\\n]*)`,`((?:[rRbBfFuU]{0,2})(?:"""[\\s\\S]*?"""|'''[\\s\\S]*?'''))`,`((?:[rRbBfFuU]{0,2})(?:"(?:[^"\\\\\\n]|\\\\.)*"|'(?:[^'\\\\\\n]|\\\\.)*'))`,`(@[A-Za-z_][\\w.]*)`,`(\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)`,`([A-Za-z_]\\w*)`].join(`|`),`g`);function Mn(e){let t=``,n=0,r=``;jn.lastIndex=0;for(let i=jn.exec(e);i;i=jn.exec(e)){t+=R(e.slice(n,i.index)),n=jn.lastIndex;let[a,o,s,c,l,u,d]=i;if(o)t+=`<span class="hl-c">${R(a)}</span>`;else if(s)t+=`<span class="hl-s hl-doc">${R(a)}</span>`;else if(c)t+=`<span class="hl-s">${R(a)}</span>`;else if(l)t+=`<span class="hl-d">${R(a)}</span>`;else if(u)t+=`<span class="hl-n">${R(a)}</span>`;else if(d){let e=On.has(d)?`hl-k`:kn.has(d)?`hl-k hl-const`:r===`class`?`hl-cls`:r===`def`?`hl-f`:An.has(d)?`hl-b`:/^[A-Z]\w*$/.test(d)&&d.length>1&&/[a-z]/.test(d)?`hl-t`:``;t+=e?`<span class="${e}">${R(d)}</span>`:R(d),r=d;continue}/^\s*$/.test(a)||(r=``)}return t+R(e.slice(n))}function Nn(e){let t=/("(?:[^"\\\n]|\\.)*")(\s*:)?|\b(true|false|null)\b|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)/g,n=``,r=0;for(let i=t.exec(e);i;i=t.exec(e)){n+=R(e.slice(r,i.index)),r=t.lastIndex;let[,a,o,s,c]=i;n+=a?o?`<span class="hl-key">${R(a)}</span>${R(o)}`:`<span class="hl-s">${R(a)}</span>`:s?`<span class="hl-k hl-const">${s}</span>`:`<span class="hl-n">${c??``}</span>`}return n+R(e.slice(r))}var Pn={py:`python`,python:`python`,json:`json`,jsonc:`json`};function Fn(e){let t=String(e||``).toLowerCase();return Pn[t.replace(/^.*\./,``)]||Pn[t]||``}function In(e,t){let n=Fn(t);return n===`python`?Mn(e):n===`json`?Nn(e):R(e)}function Ln(e){return e.replace(/`([^`\n]+)`/g,`<code>$1</code>`).replace(/\*\*([^*\n]+)\*\*/g,`<b>$1</b>`).replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g,`$1<i>$2</i>`).replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g,`<a class="lnk" href="$2" target="_blank" rel="noopener">$1</a>`)}function Rn(e){let t=[],n=0;for(;;){let r=e.indexOf("```",n);if(r<0)return t.push({t:`text`,s:e.slice(n)}),t;t.push({t:`text`,s:e.slice(n,r)});let i=e.indexOf(`
`,r+3),a=e.slice(r+3,i<0?e.length:i).trim(),o=i<0?e.length:i+1,s=e.indexOf("```",o);if(s<0)return t.push({t:`code`,s:e.slice(o),lang:a}),t;t.push({t:`code`,s:e.slice(o,s),lang:a}),n=s+3}}var zn=/^\s*\|.*\|\s*$/;function Bn(e){return Rn(String(e||``)).map(e=>{if(e.t===`code`)return`<pre><code class="hl">${In(e.s,e.lang)}</code></pre>`;let t=R(e.s).split(`
`),n=[];for(let e=0;e<t.length;e++){let r=t[e]??``,i;if(i=r.match(/^(#{1,6})\s+(.*)$/))n.push(`<div class="md-h md-h${Math.min(i[1].length,4)}">${Ln(i[2])}</div>`);else if(/^\s*(-{3,}|\*{3,})\s*$/.test(r))n.push(`<hr class="md-hr">`);else if(i=r.match(/^\s*&gt;\s?(.*)$/))n.push(`<div class="md-q">${Ln(i[1])}</div>`);else if(i=r.match(/^\s*[-*]\s+(.*)$/))n.push(`<div class="md-li">${Ln(i[1])}</div>`);else if(i=r.match(/^\s*(\d+)[.)]\s+(.*)$/))n.push(`<div class="md-li md-ol"><span class="md-n">${i[1]}.</span>${Ln(i[2])}</div>`);else if(zn.test(r)&&/^\s*\|[\s:|-]+\|\s*$/.test(t[e+1]??``)){let i=e=>e.trim().replace(/^\||\|$/g,``).split(`|`).map(e=>Ln(e.trim())),a=i(r);e+=2;let o=[];for(;e<t.length&&zn.test(t[e]??``);)o.push(i(t[e++]??``));e--,n.push(`<table class="md-t"><tr>${a.map(e=>`<th>${e}</th>`).join(``)}</tr>`+o.map(e=>`<tr>${e.map(e=>`<td>${e}</td>`).join(``)}</tr>`).join(``)+`</table>`)}else n.push(r.trim()===``?`<div class="md-gap"></div>`:`<div class="md-p">${Ln(r)}</div>`)}return n.join(``)}).join(``)}function Vn(e,t){let n=String(e||``),r=n.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/),i=``,a=n;if(r){a=r[2]??``;let e=(r[1]??``).split(`
`).map(e=>e.match(/^([\w-]+):\s*(.*)$/)).filter(e=>!!e).map(([,e,t])=>`<tr><td class="jmono">${R(e)}</td><td>${R(t)}</td></tr>`).join(``);i=e?`<table class="md-front">${e}</table>`:``}let o=Bn(a);return`<div class="md-doc">${i}${t?t(o):o}</div>`}function Hn(e){return Un(R(e))}var Un=e=>e.replace(/\$\{?([A-Za-z_]\w*)\}?/g,`<span class="pv">$&</span>`).replace(/\{\{contract\}\}/g,`<span class="pv pc">{{contract}}</span>`);function Wn(e){let t=e.match(/^(TELEMETRY [^\n]*)\n+([\s\S]*)$/);return t?{telemetry:t[1]??``,body:t[2]??``}:{telemetry:``,body:e}}var Gn=Ke[Ue].tokens,B=c`
  ${c`
  :host {
    ${s(Ge.map(e=>e.derive?`--${e.name}: var(${e.prop}, ${e.derive});`:`--${e.name}: var(${e.prop}, var(${qe(e.name)}, ${Gn[e.name]}));`).join(`
    `))}
    --sans: var(--ca-sans, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif);
    --mono: var(--ca-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace);
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    color-scheme: var(--ca-color-scheme, var(${s(qe(`color-scheme`))}, ${s(Ke[Ue].scheme)}));
    color: var(--text);
  }
  :host([hidden]) {
    display: none !important;
  }
`}
  *, *::before, *::after { box-sizing: border-box; }
  * { scrollbar-width: thin; scrollbar-color: var(--line2) transparent; }
  *:hover { scrollbar-color: var(--text-muted) transparent; }
  ::selection { background: var(--selection); }
  :focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; }
  button { font: inherit; color: inherit; }
  [hidden] { display: none !important; }

  .jmono, code, .mono { font-family: var(--mono); }
  /* read by screen readers, not shown: the word beside a status mark or an icon */
  .sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .jmono { font-size: 11.5px; }
  .meta { color: var(--text-muted); font-size: 11px; }
  /* a label in a tight box: it wraps at spaces and between phrases, never inside a word (Japanese included) */
  .words { word-break: keep-all; overflow-wrap: break-word; line-break: strict; }
  /* one fact of a row in .words (factLine): the line breaks between facts first, inside one only when it is wider than the box */
  .words .f { display: inline-block; max-width: 100%; }
  @supports (word-break: auto-phrase) {
    .words:lang(ja) { word-break: auto-phrase; }
  }
  .mut, .jdim { color: var(--text-muted); }
  /* text in a status colour: only on a status that applies (a count above 0 of a problem, a status word) */
  .t-failed { color: var(--status-failed); }
  .t-attention { color: var(--status-attention); }
  .t-done { color: var(--status-done); }
  .t-running { color: var(--status-running); }
  .t-muted { color: var(--status-muted); }
  a.lnk { color: var(--accent); cursor: pointer; text-decoration: none; }
  a.lnk:hover { text-decoration: underline; }

  /*
   * A status mark before a status word: ✓ done, ✕ failed, ◌ not started or waiting.
   * The shape keeps the meaning without colour; screen readers read the word only.
   */
  .mk-done::before, .mk-failed::before, .mk-pending::before { display: inline-block; margin-right: 0.35em; font-weight: 700; }
  .mk-done::before { content: '✓'; content: '✓' / ''; color: var(--status-done); }
  .mk-failed::before { content: '✕'; content: '✕' / ''; }
  .mk-pending::before { content: '◌'; content: '◌' / ''; }

  /*
   * A status as a pill, always with its word. A problem is tinted and marked (✕ failed, ◌ not started);
   * done is quiet (a ✓ and the word): it is the usual case, and the problems are what stand out.
   */
  .pill { border-radius: 999px; padding: 1px 10px; font-size: 11px; font-weight: 500; background: var(--raise); color: var(--text-2); white-space: nowrap; }
  .o-done, .o-recovered, .p-completed { background: none; padding-left: 2px; color: var(--text-2); }
  .o-done::before, .o-recovered::before, .p-completed::before { content: '✓'; content: '✓' / ''; color: var(--status-done); margin-right: 0.35em; font-weight: 700; }
  .o-failed, .p-invalid_output, .p-timeout, .p-max_turns, .p-stalled, .p-error, .p-launch_failed, .p-no_output, .p-aborted {
    background: var(--status-failed-bg); color: var(--status-failed); }
  .o-failed::before, .p-invalid_output::before, .p-timeout::before, .p-max_turns::before, .p-stalled::before, .p-error::before,
  .p-launch_failed::before, .p-no_output::before, .p-aborted::before { content: '✕'; content: '✕' / ''; margin-right: 0.35em; font-weight: 700; }
  .o-not_started, .p-invalid_input { background: var(--status-attention-bg); color: var(--status-attention); }
  .o-not_started::before, .p-invalid_input::before { content: '◌'; content: '◌' / ''; margin-right: 0.35em; font-weight: 700; }
  .o-running, .p-running { background: var(--status-running-bg); color: var(--status-running); }
  .o-waiting, .o-skipped, .p-skipped { background: var(--status-muted-bg); color: var(--status-muted); }
  .o-waiting::before { content: '◌'; content: '◌' / ''; margin-right: 0.35em; }
  /* a limit near (a subscription's usage): attention, not a failure */
  .p-near { background: var(--status-attention-bg); color: var(--status-attention); }

  /* a status as a word in a row (History, Problems, Outputs) */
  .jstop { font-weight: 600; }
  .jstop.j-completed { color: var(--text-2); font-weight: 500; }
  .jstop.j-completed::before { content: '✓'; content: '✓' / ''; color: var(--status-done); margin-right: 0.35em; font-weight: 700; }
  .jstop.j-timeout, .jstop.j-max_turns, .jstop.j-stalled, .jstop.j-error, .jstop.j-launch_failed, .jstop.j-no_output,
  .jstop.j-invalid_output, .jstop.j-aborted { color: var(--status-failed); }
  .jstop.j-timeout::before, .jstop.j-max_turns::before, .jstop.j-stalled::before, .jstop.j-error::before, .jstop.j-launch_failed::before,
  .jstop.j-no_output::before, .jstop.j-invalid_output::before, .jstop.j-aborted::before { content: '✕'; content: '✕' / ''; margin-right: 0.35em; }
  .jstop.j-invalid_input { color: var(--status-attention); }
  .jstop.j-invalid_input::before { content: '◌'; content: '◌' / ''; margin-right: 0.35em; }

  /*
   * A status as a dot (a run in the header and the run list). The shape carries it too:
   * round done, square failed, diamond attention, a breathing ring running.
   */
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--line2); flex: none; display: inline-block; }
  .dot.running { background: var(--status-running); animation: breathe 1.8s ease-in-out infinite; }
  .dot.done { background: var(--status-done); }
  .dot.attention { background: var(--status-attention); border-radius: 1px; transform: rotate(45deg) scale(0.86); }
  .dot.failed { background: var(--status-failed); border-radius: 1.5px; }
  .spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--status-running-bg);
    border-top-color: var(--status-running); animation: turn 0.9s linear infinite; flex: none; display: inline-block; }
  .kbd { font-family: var(--mono); font-size: 10px; border: 1px solid var(--line2); border-bottom-width: 2px;
    border-radius: 4px; padding: 0 4px; color: var(--text-muted); }

  .tag { font-size: 10px; padding: 0 7px; border-radius: 999px; border: 1px solid var(--line2); color: var(--text-muted); white-space: nowrap; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chip { font-size: 11px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--line); color: var(--text-muted); white-space: nowrap; }
  .chip.done { color: var(--text-2); }
  .chip.done > [aria-hidden] { color: var(--status-done); font-weight: 700; }
  .chip.cur { background: var(--status-running); color: var(--bg); border-color: var(--status-running); font-weight: 600; animation: ping 1.6s var(--ease) infinite; }
  .chip.todo { opacity: 0.65; }
  .taskchip { display: inline-block; font: inherit; font-family: var(--mono); font-size: 11px; line-height: 1.5; padding: 0 8px;
    border-radius: 999px; border: 1px solid var(--line); background: var(--raise); color: var(--text-2); white-space: nowrap; }
  button.taskchip { cursor: pointer; }
  button.taskchip:hover { border-color: var(--accent); color: var(--text); }

  .g12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 14px; }
  .c12 { grid-column: span 12; }
  .c7 { grid-column: span 7; }
  .c5 { grid-column: span 5; }
  @media (max-width: 1150px) {
    .c7, .c5 { grid-column: span 12; }
  }
  .panel { background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
    border-radius: 12px; padding: 14px 16px; min-width: 0; box-shadow: 0 10px 28px color-mix(in srgb, var(--shadow) 40%, transparent); }
  .panel > h3 { margin: 0 0 12px; display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 600; color: var(--text-2); }
  .panel > h3 .r { margin-left: auto; font-weight: 400; font-size: 11.5px; color: var(--text-muted); }
  .enter { animation: enter 0.5s var(--ease) both; }
  .sect-h { margin: 14px 0 8px; font-size: 12px; color: var(--text-2); font-weight: 600; }
  .sect-h .meta { margin-left: 8px; font-weight: 400; }

  .blank { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 60px 16px; color: var(--text-muted); text-align: center; }
  .blank .ic { font-size: 30px; opacity: 0.55; }
  .blank b { color: var(--text-2); font-weight: 600; }
  .blank a.lnk { text-decoration: underline; }
  .blank.small { padding: 24px; }

  /* a short clickable row (failures, launches) */
  .fl { padding: 7px 10px; border-radius: 8px; cursor: pointer; display: grid; grid-template-columns: auto 1fr auto; gap: 2px 10px; align-items: baseline; }
  .fl > .meta:last-child { grid-column: 1 / 4; overflow: hidden; text-overflow: ellipsis; }
  .fl:hover { background: var(--raise); }
  .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11px; color: var(--text-muted); }
  .legend > span { white-space: nowrap; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }

  /* who ran it (identity, a small cue): an agent launch or Python */
  .k-ic { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; margin-right: 7px;
    font-size: 11px; background: var(--raise); color: var(--text-muted); flex: none; }
  .k-ic.llm { background: var(--agent-bg); color: var(--agent); }
  /* a duration: it measures, it does not judge (red only for a failed attempt) */
  .jdur { position: relative; display: block; height: 6px; border-radius: 3px; background: var(--track); overflow: hidden; margin-top: 2px; }
  .jdur i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--meter); }
  .jdur i.bad { background: var(--status-failed); }

  /* contracts */
  .ct-chip { display: inline-block; padding: 1px 10px; border-radius: 999px; font-size: 11.5px; background: var(--raise); color: var(--text-2); white-space: nowrap; }
  .ct-chip b { margin-left: 4px; }
  .ct-chip.valid { background: none; box-shadow: inset 0 0 0 1px var(--line2); color: var(--text-2); }
  .ct-chip.valid::before { content: '✓'; content: '✓' / ''; color: var(--status-done); margin-right: 0.35em; font-weight: 700; }
  .ct-chip.invalid, .ct-chip.failed { background: var(--status-failed-bg); color: var(--status-failed); }
  .ct-chip.invalid::before, .ct-chip.failed::before { content: '✕'; content: '✕' / ''; margin-right: 0.35em; font-weight: 700; }
  .ct-chip.running { background: var(--status-running-bg); color: var(--status-running); }
  .ct-chip.pending { background: var(--status-muted-bg); color: var(--status-muted); }
  .ct-chip.refused { background: var(--status-attention-bg); color: var(--status-attention); }
  .ct-chip.refused::before { content: '◌'; content: '◌' / ''; margin-right: 0.35em; font-weight: 700; }
  .ct-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .drv-facts { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; font-size: 12px; }
  .drv-facts i { font-style: normal; color: var(--text-muted); margin-right: 5px; font-size: 11px; }

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
`,Kn=c`
  .jtree { font-family: var(--mono); font-size: 12px; overflow: auto; }
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
  .md-doc { padding: 10px 14px; background: var(--well); border: 1px solid var(--line); border-radius: 8px; max-height: 460px; overflow: auto; line-height: 1.55; }
  .md-doc code, .tx code { background: var(--raise); border-radius: 4px; padding: 0 4px; font-size: 0.92em; }
  .md-doc pre { background: var(--well); border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; white-space: pre-wrap; }
  .md-doc pre code, .tx pre code { background: none; padding: 0; border-radius: 0; font-size: inherit; }
  .md-front { margin-bottom: 10px; border-collapse: collapse; }
  .md-front td { padding: 2px 14px 2px 0; font-size: 12.5px; border: 0; vertical-align: top; }
  .md-front td:first-child { color: var(--text-muted); }
  .md-tele { color: var(--text-muted); font-size: 11.5px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .df-text { background: var(--well); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; font-size: 12px;
    white-space: pre-wrap; max-height: 420px; overflow: auto; margin: 0; }
  .df-tog { margin-left: auto; font-size: 11px; color: var(--accent); border: 1px solid var(--line2); border-radius: 999px;
    padding: 0 9px; cursor: pointer; background: none; }
  .df-tog:hover { background: var(--accent-bg); }
  /* a template placeholder in a prompt */
  .pv { color: var(--code-constant); background: color-mix(in srgb, var(--code-constant) 12%, transparent); border-radius: 4px; padding: 0 3px; }
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
`,V=e=>(t,n)=>{n===void 0?customElements.define(e,t):n.addInitializer(()=>{customElements.define(e,t)})},qn={attribute:!0,type:String,converter:S,reflect:!1,hasChanged:C},Jn=(e=qn,t,n)=>{let{kind:r,metadata:i}=n,a=globalThis.litPropertyMetadata.get(i);if(a===void 0&&globalThis.litPropertyMetadata.set(i,a=new Map),r===`setter`&&((e=Object.create(e)).wrapped=!0),a.set(n.name,e),r===`accessor`){let{name:r}=n;return{set(n){let i=t.get.call(this);t.set.call(this,n),this.requestUpdate(r,i,e,!0,n)},init(t){return t!==void 0&&this.C(r,void 0,e,t),t}}}if(r===`setter`){let{name:r}=n;return function(n){let i=this[r];t.call(this,n),this.requestUpdate(r,i,e,!0,n)}}throw Error(`Unsupported decorator location: `+r)};function H(e){return(t,n)=>typeof n==`object`?Jn(e,t,n):((e,t,n)=>{let r=t.hasOwnProperty(n);return t.constructor.createProperty(n,e),r?Object.getOwnPropertyDescriptor(t,n):void 0})(e,t,n)}function U(e){return H({...e,state:!0,attribute:!1})}var Yn=(e,t,n)=>(n.configurable=!0,n.enumerable=!0,Reflect.decorate&&typeof t!=`object`&&Object.defineProperty(e,t,n),n);function Xn(e,t){return(n,r,i)=>{let a=t=>t.renderRoot?.querySelector(e)??null;if(t){let{get:e,set:t}=typeof r==`object`?n:i??(()=>{let e=Symbol();return{get(){return this[e]},set(t){this[e]=t}}})();return Yn(n,r,{get(){let n=e.call(this);return n===void 0&&(n=a(this),(n!==null||this.hasUpdated)&&t.call(this,n)),n}})}return Yn(n,r,{get(){return a(this)}})}}function W(e,t,n,r){var i=arguments.length,a=i<3?t:r===null?r=Object.getOwnPropertyDescriptor(t,n):r,o;if(typeof Reflect==`object`&&typeof Reflect.decorate==`function`)a=Reflect.decorate(e,t,n,r);else for(var s=e.length-1;s>=0;s--)(o=e[s])&&(a=(i<3?o(a):i>3?o(t,n,a):o(t,n))||a);return i>3&&a&&Object.defineProperty(t,n,a),a}var Zn=e=>typeof e!=`object`||!e||(Array.isArray(e)?!e.length:!Object.keys(e).length),Qn=class extends A{constructor(...e){super(...e),this.open=1}static{this.styles=[B,Kn]}render(){return O`<div class="jtree">${this.node(this.value,0)}</div>`}node(e,t){if(typeof e!=`object`||!e)return O`<span class=${typeof e==`string`?`js`:`jn`}>${JSON.stringify(e)??`undefined`}</span>`;let n=Array.isArray(e)?e.map((e,t)=>[t,e]):Object.entries(e);return n.length?O`${n.map(([e,n])=>Zn(n)?O`<div class="jt"><span class="jk">${e}</span>: ${this.node(n,t+1)}</div>`:O`<details class="jt" ?open=${t<this.open}>
            <summary>
              <span class="jk">${e}</span>
              <span class="meta">${Array.isArray(n)?`[${n.length}]`:`{${Object.keys(n).length}}`}</span>
            </summary>
            ${this.node(n,t+1)}
          </details>`)}`:Array.isArray(e)?`[]`:`{}`}};W([H({attribute:!1})],Qn.prototype,`value`,void 0),W([H({type:Number})],Qn.prototype,`open`,void 0),Qn=W([V(`ca-json-tree`),P()],Qn);var $n=new Set,er=null;function tr(){for(let e of $n)e.requestUpdate()}var nr=class{constructor(e){this.host=e,e.addController(this)}hostConnected(){$n.add(this.host),er??=setInterval(tr,1e3)}hostDisconnected(){$n.delete(this.host),!$n.size&&er&&(clearInterval(er),er=null)}},rr=new class{constructor(){this.seen=new Map}at(e,t,n=Date.now()){let r=Math.round(n-t*1e3),i=this.seen.get(e);return i!==void 0&&Math.abs(i-r)<5e3?i:(this.seen.set(e,r),r)}},ir=class extends A{constructor(){super(),this.since=0,new nr(this)}createRenderRoot(){return this}render(){return this.since?F((Date.now()-this.since)/1e3):``}};W([H({type:Number})],ir.prototype,`since`,void 0),ir=W([V(`ca-elapsed`)],ir);var ar=()=>globalThis.matchMedia?.(`(prefers-reduced-motion: reduce)`).matches??!1,or=class extends A{constructor(...e){super(...e),this.value=0,this.shown=0,this.frame=0}createRenderRoot(){return this}willUpdate(e){if(!e.has(`value`))return;let t=this.shown,n=this.value;if(cancelAnimationFrame(this.frame),ar()||t===n||!Number.isFinite(n)||!this.isConnected){this.shown=n;return}let r=performance.now(),i=e=>{let a=Math.min(1,(e-r)/700);this.shown=Math.round(t+(n-t)*(1-(1-a)**3)),a<1&&(this.frame=requestAnimationFrame(i))};this.frame=requestAnimationFrame(i)}disconnectedCallback(){super.disconnectedCallback(),cancelAnimationFrame(this.frame),this.shown=this.value}render(){return String(this.shown)}};W([H({type:Number})],or.prototype,`value`,void 0),W([U()],or.prototype,`shown`,void 0),or=W([V(`ca-count`)],or);var sr={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},cr=e=>(...t)=>({_$litDirective$:e,values:t}),lr=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}},ur=class extends lr{constructor(e){if(super(e),this.it=k,e.type!==sr.CHILD)throw Error(this.constructor.directiveName+`() can only be used in child bindings`)}render(e){if(e===k||e==null)return this._t=void 0,this.it=e;if(e===xe)return e;if(typeof e!=`string`)throw Error(this.constructor.directiveName+`() called with a non-string value`);if(e===this.it)return this._t;this.it=e;let t=[e];return t.raw=t,this._t={_$litType$:this.constructor.resultType,strings:t,values:[]}}};ur.directiveName=`unsafeHTML`,ur.resultType=1;var dr=cr(ur),fr=class extends A{constructor(...e){super(...e),this.text=``,this.mark=``,this.source=!1}static{this.styles=[B,Kn,c`
      :host { display: block; }
      .bar { display: flex; justify-content: flex-end; margin-bottom: 4px; }
    `]}render(){let{telemetry:e,body:t}=Wn(this.text),n=Vn(t,this.mark===`instructions`?Un:void 0);return O`<div class="bar">
        <button type="button" class="df-tog" @click=${()=>this.source=!this.source}>
          ${this.source?N(`Show rendered`):N(`Show source`)}</button>
      </div>
      ${this.source?O`<pre class="df-text">${this.text}</pre>`:O`${e?O`<div class="md-tele jmono">${e}</div>`:k}${dr(n)}`}`}};W([H()],fr.prototype,`text`,void 0),W([H()],fr.prototype,`mark`,void 0),W([U()],fr.prototype,`source`,void 0),fr=W([V(`ca-markdown`),P()],fr);var pr=new Set([`instructions`,`schema`,`agent`]),mr=e=>{let t=e.split(`/`).filter(Boolean);return t.length>2?`…/${t.slice(-2).join(`/`)}`:e},hr=class extends A{constructor(...e){super(...e),this.definition=null,this.memory=`definition`,this.open=new Dt(`definition:open`),this.source=new Dt(`definition:source`)}static{this.styles=[B,Kn,c`
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
    `]}willUpdate(e){e.has(`memory`)&&(this.open=new Dt(`${this.memory}:open`),this.source=new Dt(`${this.memory}:source`))}render(){let e=this.definition;if(!e)return O`<div class="blank"><span class="ic" aria-hidden="true">⌘</span><b>${N(`No definition`)}</b></div>`;if(e.executor===`python`)return this.python(e);let t=e.plugin_dirs||[],n=[[N(`Role`),e.role||N(`none`)],[t.length>1?N(`Plugin directories`):N(`Plugin directory`),t.length?O`${t.map((e,t)=>O`${t?`, `:``}<span class="jmono" title=${e}>${mr(e)}</span>`)}`:N(`none`)],[N(`Parameters`),e.params||N(`none`)],[N(`Output`),e.output||N(`none`)],...(e.validators||[]).length?[[N(`Other checks`),(e.validators||[]).join(`, `)]]:[]],r=Array.isArray(e.declared)?e.declared:[],i=t=>t.part===`agent`&&!!e.role&&t.path.replace(/^.*\//,``)===`${e.role}.md`,a=[...e.files||[]].sort((e,t)=>Number(i(t))-Number(i(e)));return O`<div class="drv-facts" style="margin-bottom:10px">${n.map(([e,t])=>O`<span><i>${e}</i>${t}</span>`)}</div>
      ${r.length?O`<h4 class="sect-h">${N(`Checked files`)}</h4>
            ${r.map(e=>O`<div class="ct-in">
                <span class="ct-chip">${e.io}</span><span class="jmono">${e.path}</span>
                <span class="meta" title=${N(`The schema the file is checked against`)}>${N(M`Schema ${e.schema}`)}</span>
              </div>`)}`:k}
      ${a.length?O`<h4 class="sect-h">${N(`Files`)}</h4>${a.map(t=>this.file(t,i(t),!!e.role))}`:O`<div class="meta">${N(O`No files | defined in Python code (<code>TaskAdapter</code>)`)}</div>`}`}python(e){let t=(e.files||[]).find(e=>e.part===`source`),n=e.line??1,r=t?t.text.replace(/\n$/,``).split(`
`).length:0,i=[[N(`Parameters`),e.params&&e.params!==`none`?e.params:N(`none`)],[N(`Output`),e.output&&e.output!==`none`?e.output:N(`none`)],...(e.validators||[]).length?[[N(`Other checks`),(e.validators||[]).join(`, `)]]:[]];return O`${e.signature?O`<div class="py-sig hl">${dr(In(`def ${e.signature}`,`python`))}</div>`:k}
      <div class="py-where">
        ${e.function??e.kind}${e.file?O` | <span title=${e.file}>${e.file.replace(/^.*\//,``)}${e.line?`:${e.line}`:``}</span>`:k}
      </div>
      ${e.doc?O`<div class="py-doc">${e.doc}</div>`:k}
      <div class="drv-facts" style="margin-bottom:12px">${i.map(([e,t])=>O`<span><i>${e}</i>${t}</span>`)}</div>
      ${t?O`<h4 class="sect-h">${N(`Source`)}</h4>
            <div class="src">
              <pre class="ln">${Array.from({length:r},(e,t)=>n+t).join(`
`)}</pre>
              <pre class="hl">${dr(In(t.text.replace(/\n$/,``),`python`))}</pre>
            </div>`:k}`}file(e,t=!1,n=!1){let r=`${e.part}|${e.path}`,i=/\.md$/i.test(e.path),a=e.part===`instructions`,o=!i||this.source.has(r),s=e.part===`agent`&&n?t:pr.has(e.part);return O`<details class="df" ?open=${this.open.has(r)||s&&!this.open.has(`closed:${r}`)} @toggle=${e=>{let t=e.target.open;this.open.set(r,t),this.open.set(`closed:${r}`,!t)}}>
      <summary>
        <span class="tag">${e.part}</span><span class="jmono">${e.path}</span>
        ${t?O`<span class="ct-chip">${N(`Role of this kind`)}</span>`:k}
        ${i?O`<button type="button" class="df-tog" @click=${e=>{e.preventDefault(),this.source.set(r,!this.source.has(r)),this.requestUpdate()}}>${N(o?`Show rendered`:`Show source`)}</button>`:k}
      </summary>
      ${o?O`<pre class="df-text"><code class="hl">${dr(a?Hn(e.text):In(e.text,e.path))}</code></pre>`:dr(Vn(e.text,a?Un:void 0))}
    </details>`}};W([H({attribute:!1})],hr.prototype,`definition`,void 0),W([H()],hr.prototype,`memory`,void 0),hr=W([V(`ca-definition`),P()],hr);var gr=new Set([`launch`,`message_update`,`tool_execution_start`,`tool_execution_update`,`tool_execution_end`,`acall`,`aresult`,`message_start`,`message_end`,`turn_end`,`notice`,`auto_retry_start`]);function _r(e){return gr.has(e.type)?e:null}var vr=/\{[^{}]+\}/g,yr=()=>typeof process==`object`&&Number.parseInt(process?.versions?.node?.substring(0,2))>=18&&process.versions.undici;function br(){return Math.random().toString(36).slice(2,11)}function xr(e){let{baseUrl:t=``,Request:n=globalThis.Request,fetch:r=globalThis.fetch,querySerializer:i,bodySerializer:a,pathSerializer:o,headers:s,requestInitExt:c=void 0,...l}={...e};c=yr()?c:void 0,t=Ar(t);let u=[];async function d(e,d){let{baseUrl:f,fetch:p=r,Request:m=n,headers:h,params:g={},parseAs:_=`json`,querySerializer:v,bodySerializer:y=a??Dr,pathSerializer:b,body:x,middleware:S=[],...C}=d||{},ee=t;f&&(ee=Ar(f)??t);let w=typeof i==`function`?i:Tr(i);v&&(w=typeof v==`function`?v:Tr({...typeof i==`object`?i:{},...v}));let te=b||o||Er,ne=x===void 0?void 0:y(x,kr(s,h,g.header)),re=kr(ne===void 0||ne instanceof FormData?{}:{"Content-Type":`application/json`},s,h,g.header),ie=[...u,...S],ae={redirect:`follow`,...l,...C,body:ne,headers:re},T,oe,E=new m(Or(e,{baseUrl:ee,params:g,querySerializer:w,pathSerializer:te}),ae),D;for(let e in C)e in E||(E[e]=C[e]);if(ie.length){T=br(),oe=Object.freeze({baseUrl:ee,fetch:p,parseAs:_,querySerializer:w,bodySerializer:y,pathSerializer:te});for(let t of ie)if(t&&typeof t==`object`&&typeof t.onRequest==`function`){let n=await t.onRequest({request:E,schemaPath:e,params:g,options:oe,id:T});if(n){if(n instanceof m)E=n;else if(n instanceof Response){D=n;break}else throw Error(`onRequest: must return new Request() or Response() when modifying the request`)}}}if(!D){try{D=await p(E,c)}catch(t){let n=t;if(ie.length)for(let t=ie.length-1;t>=0;t--){let r=ie[t];if(r&&typeof r==`object`&&typeof r.onError==`function`){let t=await r.onError({request:E,error:n,schemaPath:e,params:g,options:oe,id:T});if(t){if(t instanceof Response){n=void 0,D=t;break}if(t instanceof Error){n=t;continue}throw Error(`onError: must return new Response() or instance of Error`)}}}if(n)throw n}if(ie.length)for(let t=ie.length-1;t>=0;t--){let n=ie[t];if(n&&typeof n==`object`&&typeof n.onResponse==`function`){let t=await n.onResponse({request:E,response:D,schemaPath:e,params:g,options:oe,id:T});if(t){if(!(t instanceof Response))throw Error(`onResponse: must return new Response() when modifying the response`);D=t}}}}let se=D.headers.get(`Content-Length`);if(D.status===204||E.method===`HEAD`||se===`0`&&!D.headers.get(`Transfer-Encoding`)?.includes(`chunked`))return D.ok?{data:void 0,response:D}:{error:void 0,response:D};if(D.ok)return{data:await(async()=>{if(_===`stream`)return D.body;if(_===`json`&&!se){let e=await D.text();return e?JSON.parse(e):void 0}return await D[_]()})(),response:D};let ce=await D.text();try{ce=JSON.parse(ce)}catch{}return{error:ce,response:D}}return{request(e,t,n){return d(t,{...n,method:e.toUpperCase()})},GET(e,t){return d(e,{...t,method:`GET`})},PUT(e,t){return d(e,{...t,method:`PUT`})},POST(e,t){return d(e,{...t,method:`POST`})},DELETE(e,t){return d(e,{...t,method:`DELETE`})},OPTIONS(e,t){return d(e,{...t,method:`OPTIONS`})},HEAD(e,t){return d(e,{...t,method:`HEAD`})},PATCH(e,t){return d(e,{...t,method:`PATCH`})},TRACE(e,t){return d(e,{...t,method:`TRACE`})},use(...e){for(let t of e)if(t){if(typeof t!=`object`||!(`onRequest`in t||`onResponse`in t||`onError`in t))throw Error("Middleware must be an object with one of `onRequest()`, `onResponse() or `onError()`");u.push(t)}},eject(...e){for(let t of e){let e=u.indexOf(t);e!==-1&&u.splice(e,1)}}}}function Sr(e,t,n){if(t==null)return``;if(typeof t==`object`)throw Error("Deeply-nested arrays/objects aren’t supported. Provide your own `querySerializer()` to handle these.");return`${e}=${n?.allowReserved===!0?t:encodeURIComponent(t)}`}function Cr(e,t,n){if(!t||typeof t!=`object`)return``;let r=[],i={simple:`,`,label:`.`,matrix:`;`}[n.style]||`&`;if(n.style!==`deepObject`&&n.explode===!1){for(let e in t)r.push(e,n.allowReserved===!0?t[e]:encodeURIComponent(t[e]));let i=r.join(`,`);switch(n.style){case`form`:return`${e}=${i}`;case`label`:return`.${i}`;case`matrix`:return`;${e}=${i}`;default:return i}}for(let i in t){let a=n.style===`deepObject`?`${e}[${i}]`:i;r.push(Sr(a,t[i],n))}let a=r.join(i);return n.style===`label`||n.style===`matrix`?`${i}${a}`:a}function wr(e,t,n){if(!Array.isArray(t))return``;if(n.explode===!1){let r={form:`,`,spaceDelimited:`%20`,pipeDelimited:`|`}[n.style]||`,`,i=(n.allowReserved===!0?t:t.map(e=>encodeURIComponent(e))).join(r);switch(n.style){case`simple`:return i;case`label`:return`.${i}`;case`matrix`:return`;${e}=${i}`;default:return`${e}=${i}`}}let r={simple:`,`,label:`.`,matrix:`;`}[n.style]||`&`,i=[];for(let r of t)n.style===`simple`||n.style===`label`?i.push(n.allowReserved===!0?r:encodeURIComponent(r)):i.push(Sr(e,r,n));return n.style===`label`||n.style===`matrix`?`${r}${i.join(r)}`:i.join(r)}function Tr(e){return function(t){let n=[];if(t&&typeof t==`object`)for(let r in t){let i=t[r];if(i!=null){if(Array.isArray(i)){if(i.length===0)continue;n.push(wr(r,i,{style:`form`,explode:!0,...e?.array,allowReserved:e?.allowReserved||!1}));continue}if(typeof i==`object`){n.push(Cr(r,i,{style:`deepObject`,explode:!0,...e?.object,allowReserved:e?.allowReserved||!1}));continue}n.push(Sr(r,i,e))}}return n.join(`&`)}}function Er(e,t){let n=e;for(let r of e.match(vr)??[]){let e=r.substring(1,r.length-1),i=!1,a=`simple`;if(e.endsWith(`*`)&&(i=!0,e=e.substring(0,e.length-1)),e.startsWith(`.`)?(a=`label`,e=e.substring(1)):e.startsWith(`;`)&&(a=`matrix`,e=e.substring(1)),!t||t[e]===void 0||t[e]===null)continue;let o=t[e];if(Array.isArray(o)){n=n.replace(r,wr(e,o,{style:a,explode:i}));continue}if(typeof o==`object`){n=n.replace(r,Cr(e,o,{style:a,explode:i}));continue}if(a===`matrix`){n=n.replace(r,`;${Sr(e,o)}`);continue}n=n.replace(r,a===`label`?`.${encodeURIComponent(o)}`:encodeURIComponent(o))}return n}function Dr(e,t){return e instanceof FormData?e:t&&(t.get instanceof Function?t.get(`Content-Type`)??t.get(`content-type`):t[`Content-Type`]??t[`content-type`])===`application/x-www-form-urlencoded`?new URLSearchParams(e).toString():JSON.stringify(e)}function Or(e,t){let n=`${t.baseUrl}${e}`;t.params?.path&&(n=t.pathSerializer(n,t.params.path));let r=t.querySerializer(t.params.query??{});return r.startsWith(`?`)&&(r=r.substring(1)),r&&(n+=`?${r}`),n}function kr(...e){let t=new Headers;for(let n of e){if(!n||typeof n!=`object`)continue;let e=n instanceof Headers?n.entries():Object.entries(n);for(let[n,r]of e)if(r===null)t.delete(n);else if(Array.isArray(r))for(let e of r)t.append(n,e);else r!==void 0&&t.set(n,r)}return t}function Ar(e){return e.endsWith(`/`)?e.substring(0,e.length-1):e}var jr=class extends Error{constructor(e,t){super(`${e} ${t}`),this.status=e,this.path=t,this.name=`ApiError`}};async function Mr(e){let{data:t,response:n}=await e;if(!n.ok||t===void 0)throw new jr(n.status,new URL(n.url,`http://x`).pathname);return t}function Nr(e={}){let t=(e.baseUrl??``).replace(/\/$/,``),n=xr({baseUrl:t||globalThis.location?.origin||``,...e.fetch?{fetch:e.fetch}:{}});return{baseUrl:t,info:()=>Mr(n.GET(`/api/info`)),runs:()=>Mr(n.GET(`/api/runs`)),journal:(e,t=0)=>Mr(n.GET(`/api/runs/{run}/journal`,{params:{path:{run:e},query:{since:t}}})),definitions:e=>Mr(n.GET(`/api/runs/{run}/definitions`,{params:{path:{run:e}}})),task:(e,t)=>Mr(n.GET(`/api/runs/{run}/task/{key}`,{params:{path:{run:e,key:t}}})),stream:(e,t,r=0)=>Mr(n.GET(`/api/runs/{run}/stream/{key}`,{params:{path:{run:e,key:t},query:{since:r}}})),panel:(e,t)=>Mr(n.GET(`/api/runs/{run}/panels/{name}`,{params:{path:{run:e,name:t}}}))}}var Pr=[`journal`,`procs`,`plan`,`outputs`,`cursor`,`ready`];function Fr(e,t,n,r){let i=new(r.EventSource??globalThis.EventSource)(e);i.onopen=()=>n.open?.(),i.onerror=()=>n.error?.();for(let e of t)i.addEventListener(e,t=>{n.message({event:e,data:JSON.parse(t.data)})});return()=>i.close()}var Ir=encodeURIComponent;function Lr(e,t,n,r={}){let i=[...Pr,...t.map(e=>`panel:${e}`)];return Fr(`${r.baseUrl??``}/events?run=${Ir(e)}`,i,n,r)}function Rr(e,t,n,r={}){return Fr(`${r.baseUrl??``}/events/stream?run=${Ir(e)}&key=${Ir(t)}`,[`stream`],{...n,message:e=>n.message(e.data)},r)}var zr=4e3;function Br(){return{journal:[],procs:null,plan:{nodes:[],groups:[],flow_calls:[]},outputs:{contracts:[],tally:{valid:0,invalid:0,refused:0,pending:0,failed:0,running:0}},cursor:null,panels:{},ready:!1}}function Vr(e,t){let n=e,r=null,i=()=>{if(!r)return;let e=n.journal.concat(r);n={...n,journal:e.length>4e3?e.slice(e.length-zr):e},r=null};for(let e of t){if(e.event===`journal`){(r??=[]).push(e.data);continue}switch(i(),e.event){case`connected`:n={...n,journal:[],ready:!1};break;case`ready`:n={...n,ready:!0};break;case`procs`:n={...n,procs:e.data};break;case`plan`:n={...n,plan:e.data};break;case`outputs`:n={...n,outputs:e.data};break;case`cursor`:n={...n,cursor:e.data};break;default:n={...n,panels:{...n.panels,[e.event.slice(6)]:e.data}}}}return i(),n}var Hr=e=>!!e.stop&&e.stop!==`completed`&&e.stop!==`skipped`,G=e=>e.executor===`python`;function Ur(e){let t=0;return e.map((n,r)=>{let i=e[r-1];return i&&(n.attempt??0)<=(i.attempt??0)&&t++,t})}var Wr=e=>`${e.ts}|${e.key}`,Gr=(e,t)=>e.find(e=>e.run===t),Kr=(e,t)=>!!e.procs?.alive||!!t?.running;function qr(e){return e?[...e.launches.map(e=>({cls:`llm`,id:`c:${e.key}`,kind:e.kind||`task`,unit:e.unit||``,detail:[e.unit,e.model||e.role].filter(Boolean).join(` | `),ageS:e.age_s,key:e.key})),...e.python_tasks.map(e=>({cls:`py`,id:`p:${e.key}`,kind:e.kind||`task`,unit:e.unit||``,detail:e.unit||`Python`,ageS:e.age_s,key:``}))]:[]}var Jr={title:`contraagent`,panels:[],api_version:``},Yr=class{constructor(e={}){this.snap={info:Jr,runs:[],run:``,state:Br(),connected:!1,fresh:new Set},this.listeners=new Set,this.rowListeners=new Set,this.closeFeed=null,this.queue=[],this.flushTimer=null,this.pollTimer=null,this.opts={runsEveryMs:5e3,batchMs:50,freshMs:4e3,...e},this.client=e.client??Nr(e.baseUrl===void 0?{}:{baseUrl:e.baseUrl})}get snapshot(){return this.snap}subscribe(e){return this.listeners.add(e),()=>this.listeners.delete(e)}onNewRow(e){return this.rowListeners.add(e),()=>this.rowListeners.delete(e)}async start(){try{let e=this.panelNames();this.set({info:await this.client.info()}),this.snap.run&&this.panelNames()!==e&&this.reopen()}catch{}await this.refreshRuns(),this.pollTimer??=setInterval(()=>void this.refreshRuns(),this.opts.runsEveryMs)}async refreshRuns(){try{this.set({runs:await this.client.runs()})}catch{}}panelNames(){return this.snap.info.panels.map(e=>e.name).join(`
`)}reopen(){let e=this.snap.run;this.closeFeed?.(),this.closeFeed=null,this.selectRun(e)}selectRun(e){(e!==this.snap.run||!this.closeFeed&&e)&&(this.closeFeed?.(),this.closeFeed=null,this.queue=[],this.set({run:e,state:Br(),connected:!1,fresh:new Set}),e&&(this.closeFeed=Lr(e,this.snap.info.panels.map(e=>e.name),{open:()=>{this.push({event:`connected`}),this.set({connected:!0})},error:()=>this.set({connected:!1}),message:e=>this.push(e)},{...this.opts.baseUrl===void 0?{}:{baseUrl:this.opts.baseUrl},...this.opts.feed})))}stop(){this.closeFeed?.(),this.closeFeed=null,this.pollTimer&&clearInterval(this.pollTimer),this.pollTimer=null,this.flushTimer&&clearTimeout(this.flushTimer),this.flushTimer=null}push(e){this.queue.push(e),this.flushTimer??=setTimeout(()=>this.flush(),this.opts.batchMs)}flush(){this.flushTimer=null;let e=this.queue;this.queue=[];let t=this.snap.state.ready,n=[];for(let r of e)r.event===`connected`?t=!1:r.event===`ready`?t=!0:r.event===`journal`&&t&&n.push(r.data);let r=Vr(this.snap.state,e);if(!n.length){this.set({state:r});return}let i=new Set(this.snap.fresh);for(let e of n)i.add(Wr(e));this.set({state:r,fresh:i});for(let e of n)for(let t of this.rowListeners)t(e);setTimeout(()=>{let e=new Set(this.snap.fresh);for(let t of n)e.delete(Wr(t));this.set({fresh:e})},this.opts.freshMs)}set(e){this.snap={...this.snap,...e};for(let e of this.listeners)e(this.snap)}},Xr=e=>e.ok,K=e=>e.stop!==`invalid_input`&&e.stop!==`skipped`;function Zr(e,t){if(e?.state===`running`)return`running`;let n=t[t.length-1];return n?n.stop===`skipped`?`skipped`:n.stop===`invalid_input`?`not_started`:Xr(n)?t.some(e=>!Xr(e))?`recovered`:`done`:`failed`:e?.state===`blocked`?`not_started`:`waiting`}function Qr(e,t){let n=new Map;for(let t of e){let e=n.get(t.key);e||n.set(t.key,e=[]),e.push(t)}let r=new Map(t.nodes.map(e=>[e.key,e])),i=[...new Set([...t.nodes.map(e=>e.key),...n.keys()])],a=new Map;for(let e of i){let t=r.get(e),i=n.get(e)??[],o=i[0];a.set(e,{key:e,kind:t?.kind??o?.kind??``,unit:t?.unit??o?.unit??``,executor:t?.executor??o?.executor??`agent`,outcome:Zr(t,i),attempts:i,tries:i.filter(K),cause:null})}let o=(e,t)=>{for(let n of r.get(e)?.after??[]){if(t.has(n))continue;t.add(n);let e=a.get(n);if(e?.outcome===`failed`)return n;if(e?.outcome===`not_started`){let e=o(n,t);if(e)return e}}return null};for(let e of a.values())e.outcome===`not_started`&&(e.cause=o(e.key,new Set));return a}function $r(e){let t=new Map;for(let n of e.values())n.outcome===`failed`&&t.set(n.key,{task:n,stopped:[]});let n=[];for(let r of e.values()){if(r.outcome!==`not_started`)continue;let e=r.cause?t.get(r.cause):void 0;e?e.stopped.push(r):n.push(r)}let r=e=>e.attempts[e.attempts.length-1]?.ts??``;return{failed:[...t.values()].sort((e,t)=>r(t.task).localeCompare(r(e.task))),notStarted:n}}function ei(e){let t={done:0,recovered:0,failed:0,not_started:0,running:0,waiting:0,skipped:0,total:0};for(let n of e.values())t[n.outcome]++,t.total++;return t}function ti(e){let t=Array.isArray(e?.flow)?e.flow:[];for(let e=t.length-1;e>=0;e--){let n=t[e]?.loops??[],r=n[n.length-1];if(r)return typeof r.pass==`number`&&r.pass>=1?r.pass:1}return null}var ni=new Set([`done`,`recovered`,`skipped`]);function ri(e,t){let n=Qr(e,t),r=new Map(t.nodes.map(e=>[e.key,e]));return[...n.values()].map(e=>{let t=e.attempts[e.attempts.length-1],i=r.get(e.key);return{...e,pass:ti(i),wall_s:e.tries.reduce((e,t)=>e+(t.wall_s||0),0),last_ts:t?.ts??``,last_stop:t?.stop??``,waits_for:e.outcome===`waiting`?(i?.after??[]).filter(e=>!ni.has(n.get(e)?.outcome??`waiting`)):[]}})}function ii(e){let t=e.filter(e=>e.executor!==`python`),n=t.find(e=>e.outcome===`running`);if(n)return n.key;let r=e=>e.tries[e.tries.length-1]?.ts??``;return t.filter(r).sort((e,t)=>r(t).localeCompare(r(e)))[0]?.key??null}var ai=()=>({input:0,output:0,cache_read:0,cache_creation:0,calls:0,cost:null,reported:0}),oi=e=>e.input+e.output+e.cache_read+e.cache_creation;function si(e,t){let n=t.usage;return!n&&(t.cost_usd===null||t.cost_usd===void 0)?e:(n&&(e.input+=n.input??0,e.output+=n.output??0,e.cache_read+=n.cache_read??0,e.cache_creation+=n.cache_creation??0,e.calls+=n.calls??0),t.cost_usd!==null&&t.cost_usd!==void 0&&(e.cost=(e.cost??0)+t.cost_usd),e.reported++,e)}function ci(e){let t=ai();for(let n of e)si(t,n);return t.reported?t:null}function li(e,t){let n=new Map,r=ai();for(let i of e){si(r,i);let e=t(i),a=n.get(e);a||n.set(e,a={id:e,kind:i.kind,unit:i.unit??``,spend:ai(),share:null}),si(a.spend,i)}let i=[...n.values()].filter(e=>e.spend.reported);for(let e of i)e.share=r.cost?(e.spend.cost??0)/r.cost:null;return i.sort((e,t)=>(t.spend.cost??0)-(e.spend.cost??0)||oi(t.spend)-oi(e.spend))}var ui=e=>li(e,e=>e.key),di=e=>li(e,e=>e.kind).map(e=>({...e,unit:``})),fi=e=>Date.parse(e.observed_at??``),pi=e=>!Number.isNaN(fi(e))&&(e.five_hour_pct!=null||e.seven_day_pct!=null);function mi(e){let t=[];for(let n of e)for(let e of n.quota??[])pi(e)&&t.push({reading:e,key:n.key,attempt:n.attempt??0});return t.sort((e,t)=>fi(e.reading)-fi(t.reading))}function hi(e){let t=new Map;for(let{reading:n}of mi(e)){let e=n.credential??``,r=t.get(e);r||t.set(e,r=[]),r.push(n)}let n=[];for(let[e,r]of t){let t=r[0],i=r[r.length-1];t&&i&&n.push({credential:e,first:t,last:i})}return n.sort((e,t)=>(t.last.seven_day_pct??0)-(e.last.seven_day_pct??0))}function gi(e,t){let n=(e.quota??[]).filter(pi).sort((e,t)=>fi(e)-fi(t)),r=Date.parse(e.ts),i=n[0]??null,a=i?.credential??``;return{start:i,next:(i===null||Number.isNaN(r)?void 0:t.find(e=>fi(e.reading)>r&&(e.reading.credential??``)===a))?.reading??null}}function _i(e){switch(e){case`done`:return N(`done`);case`recovered`:return N(`done after retrying`);case`failed`:return N(`failed`);case`not_started`:return N(`not started`);case`running`:return N(`running`);case`waiting`:return N(`waiting`);case`skipped`:return N(`skipped`)}}var vi=(e,t)=>e===`waiting`&&!t?N(`not run`):_i(e);function yi(e){let t=e[0];return t?e.length===1?N(M`waits for output of ${L(t)}`):N(M`waits for output of ${e.length} earlier tasks`):``}function bi(e,t){if(t)return t.outcome;let n=e[e.length-1];return n?n.stop===`invalid_input`?`not_started`:n.stop===`skipped`?`skipped`:n.ok?e.some(e=>K(e)&&!e.ok)?`recovered`:`done`:`failed`:`waiting`}function xi(e){switch(e){case`done`:return N(`done`);case`failed`:return N(`failed`);case`blocked`:return N(`not started`);case`running`:return N(`running`);case`pending`:return N(`waiting`);case`skipped`:return N(`skipped`)}}function Si(e,t){switch(e){case`done`:return N(M`${t} done`);case`recovered`:return N(M`${t} done after retrying`);case`failed`:return N(M`${t} failed`);case`not_started`:return N(M`${t} not started`);case`running`:return N(M`${t} running`);case`waiting`:return N(M`${t} waiting`);case`skipped`:return N(M`${t} skipped`);case`not_run`:return N(M`${t} not run`)}}function q(e,t){switch(e){case`completed`:return N(`done`);case`skipped`:return N(`skipped`);case`invalid_input`:{let e=new Set(Fi(t).map(e=>e.problem));return e.size===1&&e.has(`missing`)?N(`not started (input missing)`):e.size===1&&e.has(`checks`)?N(`not started (input failed checks)`):N(`not started (input missing or failed checks)`)}case`invalid_output`:return N(`failed checks`);case`timeout`:return N(`timed out`);case`max_turns`:return N(`turn limit reached`);case`budget`:return N(`cost limit reached`);case`context_budget`:return N(`context limit reached`);case`stalled`:return N(`stalled (no output)`);case`auth_failed`:return N(`authentication failed`);case`api_error`:return N(`API error`);case`rate_limited`:return N(`rate limited`);case`refused`:return N(`refused by the model`);case`aborted`:return N(`aborted`);case`denied`:return N(`permission denied`);case`error`:return N(`error`);case`no_output`:return N(`ended without a result`);case`launch_failed`:return N(`could not start the agent`);case`credential_mismatch`:return N(`wrong identity used`);case null:case void 0:case``:return`—`;default:return N(M`unknown (${e})`)}}var Ci=e=>N(M`Attempt ${(e??0)+1}`);function wi(e){let t=Ur(e),n=e.map((e,n)=>t[n]?I(Ci(e.attempt),N(`resumed run`)):Ci(e.attempt));return n.map((t,r)=>n.indexOf(t)===n.lastIndexOf(t)?t:I(t,Sn(e[r]?.ts)))}var Ti=e=>N(M`Pass ${e}`),Ei=e=>N(e<=1?`1 pass`:M`up to ${e} passes`),Di=e=>N(e<=1?`1 pass`:M`${e} passes`),Oi=e=>e.map(([e,t])=>N(e<=1?M`1 pass: ${t}`:M`${e} passes: ${t}`)).join(` | `),ki=()=>N(`loop`);function Ai(e){return e<=0?``:N(e===1?`1 correction`:M`${e} corrections`)}var ji=e=>e?e===`ambient`?N(`default`):e:``,Mi=e=>e===`ambient`?N(`local credentials (ambient)`):``,Ni=e=>e.model||e.route||`—`;function Pi(e,t){if(!e||e.length<2)return``;let n=e.map((t,n)=>n<e.length-1?N(M`${Ni(t)} (${q(t.stop)})`):Ni(t)).join(` → `);return t==null?n:`${n} | ${F(t)}`}function Fi(e){let t=/^invalid input:\s*(.*)$/s.exec(e||``);if(!t)return[];let n=[];for(let e of(t[1]??``).split(`; `)){let t=/^input from (\S+) is missing: (\S+)/.exec(e);if(t){n.push({path:t[2]??``,producer:t[1]??``,problem:`missing`});continue}if(t=/^(\S+?): required input is missing/.exec(e),t){n.push({path:t[1]??``,producer:``,problem:`missing`});continue}t=/^(\S+?): /.exec(e),t&&!n.some(e=>e.path===t?.[1])&&n.push({path:t[1]??``,producer:``,problem:`checks`})}return n}function Ii(e,t,n){return t===`checks`?N(n?M`input ${e} from ${n.name} failed checks`:M`input ${e} failed checks`):n?n.outcome===`failed`?N(M`input ${e} is missing because ${n.name} failed`):n.outcome===`not_started`?N(M`input ${e} is missing because ${n.name} did not start`):n.outcome===`done`||n.outcome===`recovered`||n.outcome===`skipped`?N(M`input ${e} from ${n.name} is missing`):N(M`input ${e} is missing because ${n.name} did not finish`):N(M`input ${e} is missing`)}function Li(e,t,n,r){let i=e.attempts[e.attempts.length-1];if(i?.stop===`invalid_input`){let e=Fi(i.reason)[0];if(!e)return J(i.reason,n);let a=e.producer||r?.(e.path)||``,o=a?t.get(a):void 0;return Ii(J(e.path,n),e.problem,o?{name:L(o),outcome:o.outcome}:void 0)}let a=e.cause?t.get(e.cause):void 0;return a?N(M`earlier task ${L(a)} failed`):``}function J(e,t){if(!e||!t)return e??``;let n=t.replace(/[.*+?^${}()|[\]\\]/g,`\\$&`);return e.replace(RegExp(`(?:/[^\\s:'"]*)?/${n}/`,`g`),``)}var Ri=6e3,zi=[`wheel`,`touchstart`,`pointerdown`,`keydown`],Bi=class{constructor(e){this.id=e,this.el=null,this.frame=0,this.restoring=!1,this.cancel=()=>{if(cancelAnimationFrame(this.frame),this.frame=0,this.restoring){this.restoring=!1;for(let e of zi)this.el?.removeEventListener(e,this.cancel)}},this.onScroll=()=>{!this.restoring&&this.el&&Tt(this.id,Math.round(this.el.scrollTop))}}attach(e){this.el!==e&&(this.detach(),this.el=e,e.addEventListener(`scroll`,this.onScroll,{passive:!0}))}detach(){this.cancel(),this.el?.removeEventListener(`scroll`,this.onScroll),this.el=null}restore(){let e=this.el;if(!e)return;this.cancel();let t=wt(this.id)??0;if(t<=0){e.scrollTop=0;return}let n=performance.now()+Ri;this.restoring=!0;for(let t of zi)e.addEventListener(t,this.cancel,{passive:!0,once:!0});let r=()=>{let i=e.scrollHeight-e.clientHeight;if(e.scrollTop=Math.min(t,i),i>=t||performance.now()>n)return this.cancel();this.frame=requestAnimationFrame(r)};r()}reset(){this.cancel(),this.el&&(this.el.scrollTop=0)}};function Vi(e,t){return e>0?t:``}function Hi(e,t){return e?`running`:t?.total?t.failed?`failed`:t.not_started?`attention`:`done`:``}function Ui(e){switch(e){case`completed`:return`done`;case`invalid_input`:return`attention`;case`skipped`:return`muted`;case`running`:return`running`;default:return`failed`}}function Wi(e){let t=e.groups.reduce((e,t)=>e+t.total,0),n=e.groups.reduce((e,t)=>e+t.done+t.skipped,0);return{total:t,done:n,pct:Math.round(100*n/Math.max(1,t))}}function Gi(e){let t=e.filter(K).length;return{tries:t,notStarted:e.length-t}}function Ki(e){let t=(...t)=>e.nodes.filter(e=>t.includes(e.state)).length;return{done:t(`done`,`skipped`),failed:t(`failed`),notStarted:t(`blocked`),left:t(`pending`,`running`)}}function qi(e){let t=Date.parse(e?.started_at??``),n=Date.parse(e?.last_ts??``);return Number.isNaN(t)||Number.isNaN(n)?null:Math.max(0,(n-t)/1e3)}var Ji={failed:5,running:4,blocked:3,pending:2,skipped:1,done:0},Yi=e=>e.reduce((e,t)=>Ji[t.state]>Ji[e]?t.state:e,`done`),Xi=e=>e.reduce((e,t)=>Ji[t]>Ji[e]?t:e,`done`),Zi=`loop:`,Qi=e=>typeof e==`string`;function $i(e){let t=e.flow;if(!Array.isArray(t))return[];let n=[];for(let e of t){let t=e;if(!t||typeof t!=`object`||!Qi(t.function))break;let r=(Array.isArray(t.loops)?t.loops:[]).filter(e=>!!e&&typeof e.line==`number`);n.push({function:t.function,file:Qi(t.file)?t.file:``,line:typeof t.line==`number`?t.line:0,loops:r.map(e=>e.line),passes:r.map(e=>typeof e.pass==`number`&&e.pass>=1?e.pass:1)})}return n}function ea(e){let t=e.flow_calls;return!Array.isArray(t)||t.length===0?null:new Map(t.filter(e=>e&&Qi(e.id)&&Qi(e.function)).map(e=>[e.id,e]))}var ta=new WeakMap;function na(e){let t=ta.get(e);if(t)return t;let n=e.nodes.map(e=>{let t=$i(e),n=e.created_from;return{n:e,frames:t,path:t.map(e=>e.function),from:Array.isArray(n)?n.filter(Qi):[],call:Qi(e.flow_call)?e.flow_call:``}}),r=new Map;for(let t of e.nodes)t.unit&&!r.has(t.unit)&&r.set(t.unit,r.size);let i={tasks:n,byKey:new Map(n.map(e=>[e.n.key,e])),calls:ea(e),unitRank:r,labels:new Map(e.groups.map(e=>[e.id,e.label]))};return ta.set(e,i),i}var ra=(e,t)=>t.every((t,n)=>e[n]===t);function ia(e){let t=e.filter(G).length;return t===0?`agent`:t===e.length?`python`:`mixed`}var aa=e=>e.slice(e.lastIndexOf(`.`)+1)||e,oa=(e,t)=>t>0?e.frames[t-1]?.loops??[]:[],sa=(e,t)=>t>0?e.frames[t-1]?.passes??[]:[];function ca(e,t){for(let n=0;n<Math.max(e.length,t.length);n++){let r=(e[n]??0)-(t[n]??0);if(r)return r}return 0}var la=e=>e.map((t,n)=>`${Zi}${e.slice(0,n+1).join(`.`)}`);function ua(e,t){let n=oa(e,t),r=n.length?`@${n.join(`.`)}`:``;if(e.path.length<=t)return{id:`kind:${e.n.group}${r}`,type:`kind`,name:e.n.group,loops:n};let i=e.path[t];return{id:`flow:${i}${r}`,type:`flow`,name:i,loops:n}}function da(e,t,n){if(!e.call)return{id:`>${t}`,own:!1};let r=e.call.split(`.`),i=r.map((e,t)=>r.slice(0,t+1).join(`.`)),a=0,o=0;if(n)for(let r=1;r<i.length;r++){let s=n.get(i[r])?.function,c=s===void 0?-1:e.frames.findIndex((e,t)=>t>o&&e.function===s);if(c<0||c>t)break;a=r,o=c}else a=Math.min(t,i.length-1),o=a;let s=i[a];return o===t?{id:s,own:!0}:{id:`${s}>${t}`,own:!1}}var fa={running:`running`,returned:`done`,raised:`failed`,closed:`failed`},pa=e=>e?.state===`raised`||e?.state===`closed`;function ma(e,t){let n=e.map(e=>e.n);return{key:(n.find(e=>e.state===`running`)??n[n.length-1]??{key:``}).key,unit:t,state:Yi(n),count:n.length,keys:n.map(e=>e.key)}}var ha=(e,t,n)=>{let r=e.get(t);r?r.push(n):e.set(t,[n])};function ga(e){let t=new Map,n=[];for(let r of e)r.n.unit?ha(t,r.n.unit,r):n.push(ma([r],``));return{byUnit:new Map([...t].map(([e,t])=>[e,ma(t,e)])),single:n}}function _a(e,t,n){let r=new Map;for(let i of e){let{id:e,own:a}=da(i,t,n);(r.get(e)??r.set(e,{id:e,own:a,tasks:[],unit:``}).get(e))?.tasks.push(i)}for(let e of r.values()){let t=new Set(e.tasks.map(e=>e.n.unit||``));e.unit=t.size===1?[...t][0]:``}return[...r.values()]}function va(e,t,n,r){let i=(e,t)=>{let i=e.map(e=>e.own?r?.get(e.id):void 0),a=e.map((e,t)=>{let n=i[t],r=Yi(e.tasks.map(e=>e.n));return n&&fa[n.state]?Xi([fa[n.state],r]):r}),o=e.flatMap(e=>e.tasks),s=o.map(e=>e.n.key),c=e.find((e,t)=>a[t]===`running`)??e[e.length-1],l=i.find(pa),u={key:c?.id??``,unit:t,state:Xi(a),count:s.length,keys:s,flow:n,counts:ya(o)};return l?{...u,error:l.error??``}:u},a=new Map,o=[],s=_a(e,t,r);for(let e of s)e.unit?ha(a,e.unit,e):o.push(i([e],``));let c=r?s.filter(e=>e.own&&pa(r.get(e.id))).length:0;return{byUnit:new Map([...a].map(([e,t])=>[e,i(t,e)])),single:o,calls:s.length,errors:c}}function ya(e){let t={total:e.length,done:0,failed:0,running:0,pending:0,skipped:0,blocked:0};for(let n of e)t[n.n.state]+=1;return t}function ba(e,t){let n=new Map;for(let r of e){let e=r.n.unit||``,i=n.get(e);(!i||ca(sa(r,t),i)>0)&&n.set(e,sa(r,t))}return e.filter(e=>ca(sa(e,t),n.get(e.n.unit||``)??[])===0)}function xa(e,t){let n=new Map;for(let r of e){let e=r.n.unit||``;(n.get(e)??n.set(e,new Set).get(e))?.add(sa(r,t).join(`.`))}return new Map([...n].map(([e,t])=>[e,t.size]))}var Sa=(e,t)=>t&&t>1?{...e,passes:t}:e,Ca=(e,t)=>`${e}\u0000${t}`;function wa(e,t,n){let r=new Set(e),i=new Map(e.map(e=>[e,[]]));for(let[e,n]of t)e!==n&&r.has(e)&&r.has(n)&&!i.get(e)?.includes(n)&&i.get(e)?.push(n);let a=new Set,o=new Map;for(let t of e){if(o.has(t))continue;o.set(t,1);let e=[[t,0]];for(;e.length;){let t=e[e.length-1],n=i.get(t[0])??[];if(t[1]<n.length){let r=n[t[1]++],i=o.get(r);i===1?a.add(Ca(t[0],r)):i||(o.set(r,1),e.push([r,0]))}else o.set(t[0],2),e.pop()}}let s=new Map(e.map(e=>[e,[]])),c=new Map(e.map(e=>[e,[]]));for(let[e,t]of i)for(let n of t)a.has(Ca(e,n))||(s.get(e)?.push(n),c.get(n)?.push(e));let l=new Map(e.map(e=>[e,c.get(e)?.length??0])),u=e.filter(e=>!l.get(e)),d=new Map;for(let e=u.shift();e!==void 0;e=u.shift()){d.set(e,n.get(e)??Math.max(0,...(c.get(e)??[]).map(e=>(d.get(e)??0)+1)));for(let t of s.get(e)??[])l.set(t,(l.get(t)??0)-1),l.get(t)||u.push(t)}return d}function Ta(e,t,n,r){let i=0,a=new Map;for(let[e,i]of t){let t=r.get(e);t!==void 0&&ha(a,t,[n.get(e)??0,n.get(i)??0])}for(let e of a.values())for(let t=0;t<e.length;t++)for(let n=t+1;n<e.length;n++){let[r,a]=e[t],[o,s]=e[n];(r-o)*(a-s)<0&&i++}return e.length?i:0}var Y=e=>e.startsWith(`~`);function Ea(e,t,n){let r=new Map;e.forEach((e,t)=>e.forEach(e=>r.set(e,t)));let i=new Map,a=new Map;for(let[e,n]of t)ha(a,e,n),ha(i,n,e);let o=new Map,s=e=>e.forEach((e,t)=>o.set(e,t)),c=e.map(e=>[...e]);c.forEach(s);let l=()=>Ta(c,t,o,r),u=c.map(e=>[...e]),d=l(),f=(e,t)=>{let r=new Map;for(let n of e){let e=(t.get(n)??[]).map(e=>o.get(e)).filter(e=>e!==void 0);r.set(n,e.length?e.reduce((e,t)=>e+t,0)/e.length:o.get(n)??0)}let i=e=>r.get(e)??0;if(!n)return[...e].sort((e,t)=>i(e)-i(t)||(o.get(e)??0)-(o.get(t)??0));let a=e.filter(e=>!Y(e)),s=e.filter(Y).sort((e,t)=>i(e)-i(t)||(o.get(e)??0)-(o.get(t)??0)),c=[],l=0;for(let e of a){for(;l<s.length&&i(s[l])<i(e);)c.push(s[l++]);c.push(e)}return[...c,...s.slice(l)]};for(let e=0;e<4;e++){let t=e%2==0,n=t?c.map((e,t)=>t).slice(1):c.map((e,t)=>t).reverse().slice(1);for(let e of n){let n=f(c[e],t?i:a);c[e]=n,s(n)}let r=l();r<d&&(d=r,u=c.map(e=>[...e]))}return l()<=d?c:u}function Da(e,t,n,r=!1){let i=na(e),a=t.length,o=i.tasks.filter(e=>ra(e.path,t)),s=new Map,c=new Map;for(let e of o){let t=ua(e,a);(s.get(t.id)??s.set(t.id,{...t,tasks:[]}).get(t.id))?.tasks.push(e),c.set(e.n.key,t.id)}let l=new Map,u=new Map,d=new Map,f=new Map;for(let e of s.values()){let t=la(e.loops),n=t[t.length-1]??null;t.forEach((e,n)=>f.set(e,t[n-1]??null)),n&&d.set(e.id,n);let r=n?ba(e.tasks,a):e.tasks;u.set(e.id,r);let o=e.type===`kind`?ga(r):va(r,a,e.name,i.calls);if(n){let t=xa(e.tasks,a);o.byUnit=new Map([...o.byUnit].map(([e,n])=>[e,Sa(n,t.get(e))]))}l.set(e.id,o)}let p=[...new Set([...l.values()].flatMap(e=>[...e.byUnit.keys()]))].sort((e,t)=>(i.unitRank.get(e)??0)-(i.unitRank.get(t)??0)),m=new Map,h=new Map;for(let e of s.values()){let t=la(e.loops);for(let n of e.tasks){let e=sa(n,a);t.forEach((t,r)=>{m.set(t,Math.max(m.get(t)??1,e[r]??1));let i=h.get(t)??h.set(t,new Map).get(t),a=n.n.unit||``;(i?.get(a)??i?.set(a,new Set).get(a))?.add(e.slice(0,r+1).join(`.`))})}}let g=e=>{let t=[],n=e.startsWith(`loop:`)?e:d.get(e)??null;for(;n;)t.push(n),n=f.get(n)??null;return t},_=(e,t)=>{let n=g(e);if(t===``)return n[n.length-1]??e;let r=n.indexOf(t);return r<0?void 0:r===0?e:n[r-1]},v=(e,t)=>g(e).find(e=>g(t).includes(e))??``,y=e=>e.startsWith(`stub:`)?``:d.get(e)??``,b=new Set,x=new Map,S=new Map,C=e=>{let n=0;for(;n<a&&e.path[n]===t[n];)n++;let r=ua(e,n);return{id:`stub:${n}:${r.id}`,label:r.type===`kind`?i.labels.get(r.name)??r.name:aa(r.name)}};for(let e of o){let t=c.get(e.n.key),n=(n,r)=>{let o=c.get(n);if(o===t){r===`after`&&b.add(t);return}if(o!==void 0){let s=i.byKey.get(n),c=oa(s,a),l=oa(e,a),u=0;for(;u<c.length&&c[u]===l[u];)u++;let d=ca(sa(s,a).slice(0,u),sa(e,a).slice(0,u))===0,f=`${o}\u0000${t}\u0000${r}`,p=x.get(f)??x.set(f,{from:o,to:t,type:r,tasks:new Set,samePass:!1}).get(f);p?.tasks.add(e.n.key),p&&d&&(p.samePass=!0);return}let s=i.byKey.get(n);if(!s)return;let l=C(s),u=`${l.id}\u0000${t}\u0000${r}`;(S.get(u)??S.set(u,{...l,to:t,type:r,tasks:new Set}).get(u))?.tasks.add(e.n.key)};for(let t of e.n.after??[])n(t,`after`);for(let t of e.from)n(t,`created`)}let ee=[...x.values()].filter(e=>e.type===`after`||!x.has(`${e.from}\u0000${e.to}\u0000after`)),w=[...S.values()].filter(e=>e.type===`after`||!S.has(`${e.id}\u0000${e.to}\u0000after`)),te=[``,...f.keys()],ne=new Map(te.map(e=>[e,[]]));for(let e of s.keys())for(let t of te){let n=_(e,t);n!==void 0&&!ne.get(t)?.includes(n)&&ne.get(t)?.push(n)}let re=new Map;for(let e of te){let t=ne.get(e)??[],r=e===``?n?.layers:n?.boxes[e],i=new Map;r?.forEach((e,n)=>e.forEach(e=>t.includes(e)&&i.set(e,n)));let a=ee.filter(t=>t.samePass&&v(t.from,t.to)===e).map(t=>[_(t.from,e),_(t.to,e)]);re.set(e,wa(t,a,i))}let ie=re.get(``),ae=[...new Set(w.map(e=>e.id))],T=new Map;n?.layers.forEach((e,t)=>e.forEach(e=>T.set(e,t)));let oe=new Map(ae.map(e=>[e,T.get(e)??Math.min(...w.filter(t=>t.id===e).map(e=>ie.get(_(e.to,``))??0))-1]));if([...oe.values()].some(e=>e<0)){for(let[e,t]of ie)ie.set(e,t+1);for(let[e,t]of oe)oe.set(e,t+1)}for(let[e,t]of oe)ie.set(e,t);let E=(e,t)=>re.get(e)?.get(t)??0,D=e=>Math.max(0,...re.get(e)?.values()??[]),se=(e,t)=>{let n=v(e,t);return E(n,_(e,n))>=E(n,_(t,n))},ce=ee.map(e=>({from:e.from,to:e.to,tasks:e.tasks.size,type:e.type,back:se(e.from,e.to)})),le=new Map;for(let e of te){let t=((e===``?n?.layers:n?.boxes[e])??[]).flat(),r=[...e===``?[...ae]:[],...ne.get(e)??[]];r.sort((e,n)=>{let r=t.indexOf(e),i=t.indexOf(n);return(r<0?1/0:r)-(i<0?1/0:i)});let i=Array.from({length:D(e)+1},()=>[]);for(let t of r)i[E(e,t)]?.push(t);le.set(e,i)}let ue=[],de=new Set,fe=(e,t,n,r)=>{let i=`~${e}|${t}|${n}|${r}`;return de.has(i)||(de.add(i),le.get(e)?.[r]?.push(i)),{id:i,in:e}},pe=(e,t,n,r)=>{let i=E(e,t),a=`~${e}|by:${t}|${n}|${r}|${i}`;return de.has(a)||(de.add(a),le.get(e)?.[i]?.push(a)),{id:a,in:e}},me=(e,t,n)=>{let i=e.startsWith(`stub:`)?``:v(e,t),a=y(e),o=e,s=[{id:e,in:a}];for(;a!==i;){let e=f.get(a)??``;s.push({id:a,in:e}),E(a,o)<D(a)&&s.push(pe(e,a,o,n)),o=a,a=e}let c=_(t,i);for(let e=E(i,o)+1;e<E(i,c);e++)s.push(fe(i,o,n,e));let l=g(t),u=l.slice(0,i===``?l.length:l.indexOf(i)).reverse(),d=`>${i}:${o}`,p=i;for(let e of u){let i=_(t,e);(E(e,i)>0||r)&&s.push(pe(p,e,d,n)),s.push({id:e,in:p}),p=e}return s.push({id:t,in:p}),s};for(let e of ce)e.back||ue.push({from:e.from,to:e.to,type:e.type,steps:me(e.from,e.to,e.type)});for(let e of w)ue.push({from:e.id,to:e.to,type:e.type,steps:me(e.id,e.to,e.type)});let he={};for(let e of te){let t=[],r=new Map((le.get(e)??[]).flatMap((e,t)=>e.map(e=>[e,t])));for(let n of ue)for(let i=1;i<n.steps.length;i++){let a=n.steps[i-1],o=n.steps[i];a.in===e&&o.in===e&&r.get(a.id)!==r.get(o.id)&&t.push([a.id,o.id])}let i=e===``?!!n:!!n?.boxes[e];he[e]=Ea(le.get(e)??[],t,i).map(e=>{let t=e.filter(e=>e.includes(`|by:`));return e.filter(e=>!e.includes(`|by:`)).flatMap(e=>[e,...t.filter(t=>t.includes(`|by:${e}|`))])})}let ge=e=>e.map(e=>e.filter(e=>!Y(e))),_e=[...f.keys()].map(e=>{let t=new Map;for(let[n,r]of h.get(e)??[])n&&t.set(r.size,(t.get(r.size)??0)+1);return{id:e,loop:Number(e.slice(5).split(`.`).pop()),file:o[0]?.frames[a-1]?.file??``,parent:f.get(e)??null,passes:m.get(e)??1,spread:[...t].sort((e,t)=>e[0]-t[0]),layers:ge(he[e]??[]).filter(e=>e.length)}}),ve=ge(he[``]??[]).map(e=>e.filter(e=>!e.startsWith(`stub:`))),ye=e=>{let t=l.get(e.id),n=t.byUnit.size>0;return{id:e.id,type:e.type,name:e.name,label:e.type===`kind`?i.labels.get(e.name)??e.name:aa(e.name),kinds:[...new Set(e.tasks.map(e=>e.n.kind))],executor:e.type===`flow`?null:ia(e.tasks.map(e=>e.n)),box:d.get(e.id)??null,units:n?p.map(e=>t.byUnit.get(e)??null):[],single:t.single,inOrder:b.has(e.id),counts:ya(u.get(e.id)??[]),calls:t.calls??0,errors:t.errors??0}},O=new Map(_e.map(e=>[e.id,e])),be=e=>e.flatMap(e=>e.startsWith(`loop:`)?be((O.get(e)?.layers??[]).flat()):[e]);return{graph:{path:[...t],nodes:be(ve.flat()).map(e=>ye(s.get(e))),layers:ve.filter(e=>e.length),boxes:_e,edges:ce,stubs:w.map(e=>({id:e.id,label:e.label,to:e.to,tasks:e.tasks.size,type:e.type})),units:p,slots:he,routes:ue,order:{layers:ge(he[``]??[]),boxes:Object.fromEntries(_e.map(e=>[e.id,ge(he[e.id]??[])]))}},drafts:s,ix:i}}function Oa(e,t=[],n,r=!1){return Da(e,t,n,r).graph}function ka(e){let t=na(e),n=[],r=new Set;if(t.calls)for(let e of t.calls.values())(e.state===`raised`||e.state===`closed`)&&r.add(e.id);let i=e=>r.has(e)&&![...r].some(t=>t!==e&&t.startsWith(`${e}.`));for(;;){let e=null,r=!0,a=[];for(let i of t.tasks){if(!ra(i.path,n))continue;let t=ua(i,n.length);if(t.type===`kind`||e&&e.id!==t.id){r=!1;break}e=t,a.push(i)}let o=a.some(e=>i(da(e,n.length,t.calls).id));if(!r||!e||o)return n;n.push(e.name)}}function Aa(e){let t=e[e.length-1];return t?.startsWith(`loop:`)?{path:e.slice(0,-1),loop:t}:{path:[...e],loop:null}}function ja(e,t){let{path:n,loop:r}=Aa(t),i=na(e),a=t=>!r||Oa(e,t).boxes.some(e=>e.id===r);if(i.tasks.some(e=>ra(e.path,n)))return a(n)?[...t]:null;let o=n[n.length-1];if(o===void 0)return null;let s=e=>{let t=new Map;for(let n of i.tasks)n.path.forEach((r,i)=>e(r)&&t.set(n.path.slice(0,i+1).join(`/`),n.path.slice(0,i+1)));return[...t.values()]},c=s(e=>e===o),l=c.length?c:s(e=>aa(e)===o),u=l.length===1?l[0]:null;return u&&a(u)?r?[...u,r]:u:null}function Ma(e,t){if(e.length<=t.length)return null;let n=e.slice(0,-1);return n.length<=t.length?[]:n}function Na(e,t,n,r){let{graph:i,drafts:a,ix:o}=Da(e,t,r),s=i.boxes.find(e=>e.id===n);if(!s)return null;let c=t.length,l=s.id.slice(5).split(`.`).length-1,u=new Map(i.boxes.map(e=>[e.id,e])),d=new Map(i.nodes.map(e=>[e.id,e])),f=e=>sa(e,c).slice(l),p=e=>e.layers.flat().flatMap(e=>u.has(e)?p(u.get(e)):[e]),m=e=>p(e).flatMap(e=>a.get(e)?.tasks??[]),h=(e,t)=>e.length===t.length&&ca(e,t)===0,g=(e,t)=>{let n=t.length;return[...new Set(m(e).map(f).filter(e=>e.length>n&&ca(e.slice(0,n),t)===0).map(e=>e[n]))].sort((e,t)=>e-t).flatMap(n=>{let r=[...t,n],i=e.layers.flat().flatMap(e=>{let t=u.get(e);if(t){let e=g(t,r);return e.length?[{type:`loop`,box:t,kids:e}]:[]}let n=d.get(e);return n&&a.get(e)?.tasks.some(e=>h(f(e),r))?[{type:`node`,node:n,passes:r}]:[]});return i.length?[{type:`pass`,box:e,pass:n,kids:i}]:[]})},_=g(s,[]),v=[],y=e=>e.type===`node`?1:e.kids.reduce((e,t)=>e+y(t),0),b=e=>e.type===`node`?1:1+Math.max(0,...e.kids.map(b)),x=Math.max(1,..._.map(b)),S=Array.from({length:x},()=>[]),C=(e,t)=>{let n=S[t];if(e.type===`node`){n.push({type:`node`,node:e.node,passes:e.passes,span:1,rows:x-t}),v.push({node:e.node,passes:e.passes});return}n.push(e.type===`pass`?{type:`pass`,box:e.box,pass:e.pass,span:y(e),rows:1}:{type:`loop`,box:e.box,span:y(e),rows:1});for(let n of e.kids)C(n,t+1)};for(let e of _)C(e,0);let ee=m(s),w=new Set(ee.map(e=>e.n.unit||``)),te=[...i.units.filter(e=>w.has(e)),...w.has(``)?[``]:[]],ne=new Map;v.forEach((e,t)=>{for(let n of a.get(e.node.id)?.tasks??[])h(f(n),e.passes)&&ha(ne,`${t}\u0000${n.n.unit||``}`,n)});let re=(e,t,n)=>{let r=a.get(e.node.id);if(r.type===`kind`)return ma(t,n);let i=va(t,c,r.name,o.calls);return n?i.byUnit.get(n)??i.single[0]??null:i.single[0]??null};return{box:s,columns:v,head:S,rows:te.map(e=>{let t=v.map((t,n)=>{let r=ne.get(`${n}\u0000${e}`);return r?.length?re(t,r,e):null});return{unit:e,passes:new Set(ee.filter(t=>(t.n.unit||``)===e).map(e=>sa(e,c).slice(0,l+1).join(`.`))).size,state:Xi(t.filter(e=>e!==null).map(e=>e.state)),cells:t}})}}function Pa(e,t){let n=new Map(e.map((e,t)=>[e,t])),r=e=>t===`passes`?-e.passes:t===`state`?-Ji[e.state]:0;return[...e].sort((e,t)=>r(e)-r(t)||(n.get(e)??0)-(n.get(t)??0))}function Fa(e,t,n,r,i=!1,a=10){let o=(t,n)=>e[t]?.[n]===!0,s=t=>(e[t]??[]).findIndex(Boolean),c=t=>(e[t]??[]).lastIndexOf(!0),l=(t,n,r)=>{for(let i=t;i>=0&&i<e.length;i+=n)if(o(i,r))return i;return-1},u=t=>{let r=e[t]??[],i=-1;return r.forEach((e,t)=>e&&(i<0||Math.abs(t-n)<Math.abs(i-n))&&(i=t)),i<0?null:[t,i]};switch(r){case`ArrowRight`:case`ArrowLeft`:{let i=r===`ArrowRight`?1:-1;for(let r=n+i;r>=0&&r<(e[t]?.length??0);r+=i)if(o(t,r))return[t,r];return null}case`ArrowDown`:case`ArrowUp`:{let i=r===`ArrowDown`?1:-1,a=l(t+i,i,n);if(a>=0)return[a,n];for(let n=t+i;n>=0&&n<e.length;n+=i)if(s(n)>=0)return u(n);return null}case`Home`:{let n=i?e.findIndex(e=>e.some(Boolean)):t;return n<0||s(n)<0?null:[n,s(n)]}case`End`:{let n=t;if(i)for(n=e.length-1;n>=0&&c(n)<0;n--);return n<0||c(n)<0?null:[n,c(n)]}case`PageDown`:case`PageUp`:{let n=r===`PageDown`?1:-1,i=Math.max(0,Math.min(e.length-1,t+n*a));for(let e=i;e!==t;e-=n)if(s(e)>=0)return u(e);return null}default:return null}}var Ia=(e,t,n=[])=>`${e}${n.length?`|${n.join(`.`)}`:``}#${t.unit||t.key}`;function La(e,t,n){if(!n)return null;let r=n.indexOf(`#`);if(r<0){let t=e.nodes.find(e=>e.id===n);if(t)return{type:`node`,id:n,node:t};let r=e.boxes.find(e=>e.id===n);return r?{type:`box`,id:n,box:r}:null}let[i=``,a]=n.slice(0,r).split(`|`),o=n.slice(r+1),s=e=>!!e&&(e.unit?e.unit===o:e.key===o);if(a!==void 0){if(!t)return null;let e=t.columns.findIndex(e=>e.node.id===i&&e.passes.join(`.`)===a),r=t.columns[e],o=t.rows.map(t=>t.cells[e]).find(s);return r&&o?{type:`mark`,id:n,node:r.node,mark:o,passes:r.passes}:null}let c=e.nodes.find(e=>e.id===i),l=c?[...c.units,...c.single].find(s):void 0;return c&&l?{type:`mark`,id:n,node:c,mark:l,passes:[]}:null}function Ra(e){return e<=12?{cols:Math.max(1,e),size:12}:e<=100?{cols:10,size:10}:{cols:20,size:6}}var za=e=>e.units.filter(e=>e!==null).length+e.single.length>200;function Ba(e,t){return t.filter(t=>e[t]>0).map(t=>({state:t,n:e[t],pct:100*e[t]/Math.max(1,e.total)}))}function Va(e,t,n,r){let i=new Map(e.nodes.map((e,t)=>[e.id,t])),a=[...new Set(e.edges.filter(e=>!e.back&&(n===`later`?e.from===t:e.to===t)).map(e=>n===`later`?e.to:e.from))],o=r(t);return a.sort((e,t)=>Math.abs(r(e)-o)-Math.abs(r(t)-o)||(i.get(e)??0)-(i.get(t)??0)),a[0]??null}var Ha=6,Ua={across:{gap:56,boxGap:40,sep:16,pointSep:12,pad:12,padEnd:24,margin:16},down:{gap:40,boxGap:32,sep:16,pointSep:12,pad:10,padEnd:24,margin:16}};function Wa(e,t,n){let r=[0];for(let n=1;n<e.length;n++)r.push(r[n-1]+t[n-1]);let i=[];e.forEach((e,t)=>{let a=n[t]??1;for(i.push({sum:a*(e-r[t]),w:a,n:1});i.length>1;){let e=i[i.length-1],t=i[i.length-2];if(t.sum/t.w<=e.sum/e.w)break;i.splice(-2,2,{sum:t.sum+e.sum,w:t.w+e.w,n:t.n+e.n})}});let a=[];for(let e of i)for(let t=0;t<e.n;t++)a.push(e.sum/e.w+r[a.length]);return a}function Ga(e,t,n=!1){let r=Ua[n?`down`:`across`],i=e=>n?e.h:e.w,a=e=>n?e.w:e.h,o=new Set(e.boxes.map(e=>e.id)),s=e=>t.get(`lbl:${e}`)??{w:0,h:0},c=e=>n?{u0:s(e).h+r.pad+r.gap/2,u1:r.pad,v0:r.pad,v1:r.padEnd,minU:0,minV:s(e).w+2*r.pad}:{u0:r.pad,u1:r.pad,v0:s(e).h+r.pad,v1:r.padEnd,minU:s(e).w+2*r.pad,minV:0},l=new Map,u=e=>{if(o.has(e))return l.get(e)??{u:0,v:0};if(Y(e))return{u:0,v:0};let n=t.get(e)??{w:0,h:0};return{u:i(n),v:a(n)}},d=new Map,f=new Map,p=e=>e===``?0:e.split(`.`).length,m=[``,...e.boxes.map(e=>e.id)].sort((e,t)=>p(t)-p(e)),h=(t,n)=>{let r=e.routes[t]?.steps??[],i=r[n];if(Y(i.id))return 0;if(!o.has(i.id))return u(i.id).v/2;let a=r[n-1]?.in===i.id?n-1:n+1,s=r[a];return c(i.id).v0+(d.get(i.id)?.top.get(s.id)??0)+h(t,a)};for(let t of m){let n=(e.slots[t]??[]).map(e=>[...e]);f.set(t,new Map(n.flatMap((e,t)=>e.map(e=>[e,t]))));let i=n.map(e=>Math.max(0,...e.map(e=>u(e).u))),a=t===``?r.gap:r.boxGap,s=[];i.forEach((e,t)=>s.push(t?s[t-1]+i[t-1]+a:0));let p=[];e.routes.forEach((e,n)=>e.steps.forEach((r,i)=>{let a=e.steps[i-1];i&&a&&a.in===t&&r.in===t&&f.get(t)?.get(a.id)!==f.get(t)?.get(r.id)&&p.push({a:a.id,b:r.id,oa:h(n,i-1),ob:h(n,i)})}));let m=(e,t)=>t===void 0?0:o.has(e)||o.has(t)||!(Y(e)||Y(t))?r.sep:r.pointSep,g=new Map;for(let e of n){let t=0;e.forEach((n,r)=>{g.set(n,t),t+=u(n).v+m(n,e[r+1])})}let _=(e,t)=>{let n=e.map(e=>{let n=t(e);return n.length?n.reduce((e,t)=>e+t,0)/n.length:g.get(e)??0}),r=e.map((t,n)=>u(t).v+m(t,e[n+1])),i=e.map((e,t)=>Y(e)?-1:t).filter(e=>e>=0),a=(e,t)=>r.slice(e,t).reduce((e,t)=>e+t,0),o=Wa(i.map(e=>n[e]),i.map((e,t)=>t+1<i.length?a(e,i[t+1]):0),i.map(()=>1));i.forEach((e,t)=>n[e]=o[t]),Wa(n,r,e.map(e=>Y(e)?1:1e6)).forEach((t,n)=>g.set(e[n],Math.round(t*100)/100))},v=(e,t)=>{let n=Y(e)?t:t.filter(e=>!Y(e.other));return(n.length?n:t).map(e=>e.at)},y=e=>v(e,p.filter(t=>t.b===e).map(e=>({other:e.a,at:(g.get(e.a)??0)+e.oa-e.ob}))),b=e=>v(e,p.filter(t=>t.a===e).map(e=>({other:e.b,at:(g.get(e.b)??0)+e.ob-e.oa})));for(let e=0;e<8;e++){let t=n.map((e,t)=>t);e%2&&t.reverse();for(let r of t)_(n[r],e%2?b:y)}for(let e of n)_(e,e=>[...y(e),...b(e)]);let x=g.size?Math.min(...g.values()):0;for(let[e,t]of g)g.set(e,t-x);let S=(s[s.length-1]??0)+(i[i.length-1]??0),C=Math.max(0,...n.flat().map(e=>(g.get(e)??0)+u(e).v));if(d.set(t,{rows:n,start:s,width:i,top:g,u:S,v:C}),t!==``){let e=c(t);l.set(t,{u:Math.max(e.u0+S+e.u1,e.minU),v:Math.max(e.v0+C+e.v1,e.minV)})}}let g={},_=new Map,v=(e,t,r)=>n?{x:t,y:e,w:r.v,h:r.u}:{x:e,y:t,w:r.u,h:r.v},y=(e,t,n)=>{_.set(e,{u:t,v:n});let r=d.get(e);r.rows.forEach((e,i)=>e.forEach(e=>{if(Y(e))return;let a=t+r.start[i],s=n+(r.top.get(e)??0);if(g[e]=v(a,s,u(e)),o.has(e)){let t=c(e);y(e,a+t.u0,s+t.v0)}}))};y(``,r.margin,r.margin);let b=d.get(``),x=b.u+2*r.margin,S=b.v+2*r.margin,C=(e,t)=>{let n=d.get(e),r=(_.get(e)??{u:0,v:0}).u+(n.start[t]??0);return[r,r+(n.width[t]??0)]},ee=(e,t)=>f.get(e)?.get(t)??0,w=e=>e&&Y(e.id)?/\|by:([^|]*)\|/.exec(e.id)?.[1]??``:``,te=e.routes.map((e,t)=>{let i=n=>{let r=e.steps[n];return(_.get(r.in)??{u:0,v:0}).v+(d.get(r.in)?.top.get(r.id)??0)+h(t,n)},a=e.steps.map((t,a)=>{let o=e.steps[a-1],l=e.steps[a+1],[f,p]=C(t.in,ee(t.in,t.id)),m=i(a);if(a===0)return{a:f+u(t.id).u,b:p,at:m};if(a===e.steps.length-1)return{a:f,b:f,at:m};if(Y(t.id)){let i=w(t);if(i&&o?.id===i)return{a:C(i,ee(i,e.steps[a-2]?.id??``)+1)[0],b:p,at:m};if(i&&l?.id===i){let t=ee(i,e.steps[a+2]?.id??``);return{a:f,b:t>0?C(i,t-1)[1]:(g[i]?n?g[i].y:g[i].x:f)+s(i).h+r.pad,at:m}}return{a:f,b:p,at:m}}let h=c(t.id),_=d.get(t.id);if(o?.in===t.id){if(w(l)===t.id){let e=C(t.id,ee(t.id,o.id)+1)[0];return{a:e,b:e,at:i(a+1)}}return{a:f+h.u0+_.u,b:p,at:m}}if(w(o)===t.id){let e=C(t.id,ee(t.id,l?.id??``))[0];return{a:e,b:e,at:i(a+1)}}return{a:f,b:f+h.u0,at:m}});return{from:e.from,to:e.to,type:e.type,runs:a}}),ne=e.boxes.flatMap(e=>{let t=d.get(e.id),n=_.get(e.id);if(!t||!n)return[];let r=e=>{let n=(e??[]).filter(e=>!Y(e)),r=null;for(let e of n){let n=u(e),i=(t.top.get(e)??0)+n.v;(!r||i>r.v)&&(r={u:n.u,v:i})}return r},i=t.rows.map((e,t)=>e.some(e=>!Y(e))?t:-1).filter(e=>e>=0),a=i[0]??0,o=i[i.length-1]??0,s=r(t.rows[o]),c=r(t.rows[a]);if(!s||!c)return[];let l=n.u+(t.start[o]??0)+(t.width[o]??0)/2,f=n.u+(t.start[a]??0)+(t.width[a]??0)/2;if(l-f<24){let e=Math.max(12,Math.min(28,Math.min(s.u,c.u)/4));l=(l+f)/2+e,f=l-2*e}return[{box:e.id,from:l,v0:n.v+s.v,to:f,v1:n.v+c.v,band:n.v+t.v+12}]});return{w:n?S:x,h:n?x:S,at:g,edges:te,returns:ne,down:n}}function Ka(e,t=!1,n=3){let r=e=>Math.round(e*2)/2,i=(e,n)=>t?`${r(n)},${r(e)}`:`${r(e)},${r(n)}`,a=Math.max(0,Math.min(Ha,(e.from-e.to)/2,e.band-e.v0-n,e.band-e.v1-n));return[`M${i(e.from,e.v0+n)}`,`L${i(e.from,e.band-a)}`,`Q${i(e.from,e.band)} ${i(e.from-a,e.band)}`,`L${i(e.to+a,e.band)}`,`Q${i(e.to,e.band)} ${i(e.to,e.band-a)}`,`L${i(e.to,e.v1+n)}`].join(` `)}function qa(e,t=!1){let n=e=>Math.round(e*2)/2,r=(e,r)=>t?`${n(r)},${n(e)}`:`${n(e)},${n(r)}`,i=e[0];if(!i)return``;let a=`M${r(i.a,i.at)}`;return e.forEach((t,n)=>{t.b!==t.a&&(a+=` L${r(t.b,t.at)}`);let i=e[n+1];if(!i)return;if(Math.abs(i.at-t.at)<.5){i.a!==t.b&&(a+=` L${r(i.a,i.at)}`);return}let o=(t.b+i.a)/2;a+=` C${r(o,t.at)} ${r(o,i.at)} ${r(i.a,i.at)}`}),a}function Ja(e,t,n,r){if(e<=0||t<=0||n<=0)return{k:1,x:0,y:0,h:Math.max(0,t)};let i=Math.min(1,n/e),a=Math.min(t*i,r),o=Math.min(i,a/t);return{k:o,x:(n-e*o)/2,y:(a-t*o)/2,h:a}}function Ya(e,t,n,r,i,a){let o=Math.min(a,Math.max(i,e.k*t)),s=o/e.k;return{k:o,x:n-(n-e.x)*s,y:r-(r-e.y)*s}}function Xa(e){let t=e.filter(K),n=t.filter(G),r=t.filter(e=>!G(e)),i=e=>e.reduce((e,t)=>e+(t.wall_s||0),0),a=e=>[...new Set(e.map(e=>e.key))],o=e=>a(e).length,s=t.filter(e=>(e.attempt??0)>0),c=t.filter(e=>(e.rounds||1)>1),l=t.filter(e=>(e.hops||[]).length>1);return{attempts:t.length,python:n.length,launches:r.length,bad:t.filter(e=>!e.ok).length,launchWall:i(r),pythonWall:i(n),retries:s.length,retriedTasks:o(s),retriedKeys:a(s),fixupKeys:a(c),fixups:c.reduce((e,t)=>e+(t.rounds||1)-1,0),fixupTasks:o(c),switches:l.reduce((e,t)=>e+(t.hops||[]).length-1,0),switchTasks:o(l)}}var Za=216e5,Qa=6e4;function $a(e,t,n){let r=[];for(let t of e){if(!t.ts)continue;let e=Date.parse(t.ts);if(Number.isNaN(e))continue;let n=K(t)?t.ok?G(t)?`py`:`llm`:`bad`:`idle`;r.push({lane:t.kind||`?`,cls:n,start:e-(t.wall_s||0)*1e3,end:e,live:!1,row:t})}if(!r.length&&!t.length)return null;for(let e of t)r.push({lane:e.kind,cls:`run`,start:e.t0,end:n,live:!0,liveCls:e.cls});let i=Math.max(...r.filter(e=>!e.live).map(e=>e.end),...t.map(e=>e.t0)),a=r.filter(e=>e.end>=i-Za),o=Math.min(...a.map(e=>e.start)),s=t.length?o+Math.ceil((n-o+2e4)/Qa)*Qa:i,c=[];for(let e of[...a].sort((e,t)=>e.start-t.start))c.includes(e.lane)||c.push(e.lane);let l=c.map(e=>{let t=a.filter(t=>t.lane===e).sort((e,t)=>e.start-t.start),n=[],r=t.map(({cls:e,start:t,end:r,live:i,row:a})=>{let o=n.findIndex(e=>e<=t);return o<0?o=n.push(r)-1:n[o]=r,a?{cls:e,start:t,end:r,live:i,track:o,row:a}:{cls:e,start:t,end:r,live:i,track:o}});return{name:e,llm:t.some(e=>e.cls===`llm`||e.liveCls===`llm`),bars:r,tracks:Math.max(1,n.length)}});return{t0:o,span:Math.max(1,s-o),lanes:l,hidden:r.length-a.length,live:t.length>0}}function eo(e,t,n){let r=(e.start-t.t0)/t.span*100,i=((e.live?n:e.end)-e.start)/t.span*100;return{left:r,width:Math.max(.4,e.live?Math.min(100-r,i):i)}}var to=e=>e==null?`—`:`${Math.round(e)}%`;function no(e){if(!e||e===`allowed`)return``;let t=e.split(`,`);return t.some(e=>[`rejected`,`exhausted`,`quota`,`blocked`].includes(e))?N(`limit reached`):t.every(e=>[`allowed_warning`,`warning`].includes(e))?N(`near the limit`):N(M`unknown (${e})`)}function ro(e,t=Date.now()){let n=Date.parse(e??``);if(Number.isNaN(n))return``;if(n<=t)return N(`reset`);let r=(n-t)/36e5,i=r>=48?N(M`${Math.floor(r/24)}d ${Math.floor(r%24)}h`):F((n-t)/1e3);return N(M`resets in ${i}`)}var io=e=>I(N(M`weekly ${to(e.seven_day_pct)}`),N(M`5-hour ${to(e.five_hour_pct)}`));function ao(e){let t=[e.seven_day_resets_at?N(M`Weekly usage ${to(e.seven_day_pct)} (resets ${Sn(e.seven_day_resets_at,!0)})`):N(M`Weekly usage ${to(e.seven_day_pct)}`),e.five_hour_resets_at?N(M`5-hour usage ${to(e.five_hour_pct)} (resets ${Sn(e.five_hour_resets_at,!0)})`):N(M`5-hour usage ${to(e.five_hour_pct)}`),N(M`Reported ${Sn(e.observed_at,!0)}`)],n=no(e.status);return n&&t.push(N(M`Status: ${n}`)),t.join(`
`)}var oo=e=>I(io(e),ji(e.credential));function so(e){let t=e[0];if(!t)return``;let n=e.length-1;return n?I(oo(t.last),N(n===1?`1 more account`:M`${n} more accounts`)):io(t.last)}var co=e=>e.map(e=>e.credential?`${ji(e.credential)}\n${ao(e.last)}`:ao(e.last)).join(`

`);function lo(e,t,n){return n.key?O`<button type="button" class="taskchip" title=${n.key} @click=${t=>{t.stopPropagation(),j(e,`ca-open-task`,{key:n.key,...G(n)?{view:`output`}:{}})}}>${t}</button>`:O`<span class="taskchip">${t}</span>`}var uo=e=>qi(e),fo=e=>{let t=Date.parse(e.last_ts||``);return Number.isNaN(t)?1/0:(Date.now()-t)/1e3},po=class extends A{constructor(...e){super(...e),this.runs=[],this.current=``,this.open=!1,this.q=``,this.kb=-1}static{this.styles=[B,c`
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
    `]}updated(e){e.has(`open`)&&this.open&&(this.q=``,this.kb=-1,setTimeout(()=>this.input?.focus(),30))}visible(){let e=this.q.toLowerCase().trim(),t=this.runs.filter(t=>!e||t.run.toLowerCase().includes(e)||(t.run_group||``).toLowerCase().includes(e));return[...t.filter(e=>e.running),...t.filter(e=>!e.running&&fo(e)<86400),...t.filter(e=>!e.running&&fo(e)>=86400)]}pick(e){this.close(),e!==this.current&&j(this,`ca-select-run`,{run:e})}close(){this.dispatchEvent(new Event(`close`))}onKey(e,t){if(e.key===`Escape`)return this.close();if(e.key===`ArrowDown`)this.kb=Math.min(t.length-1,this.kb+1);else if(e.key===`ArrowUp`)this.kb=Math.max(0,this.kb-1);else if(e.key===`Enter`){let e=t[Math.max(0,this.kb)];e&&this.pick(e.run);return}else return;e.preventDefault(),this.updateComplete.then(()=>this.renderRoot.querySelector(`.item.kb`)?.scrollIntoView({block:`nearest`}))}render(){let e=this.visible(),t=[[N(`Running`),e.filter(e=>e.running)],[N(`Last 24 hours`),e.filter(e=>!e.running&&fo(e)<86400)],[N(`Older`),e.filter(e=>!e.running&&fo(e)>=86400)]],n=0;return O`<div class="search">
        <input placeholder=${N(`Search runs`)} aria-label=${N(`Search runs`)} autocomplete="off" .value=${this.q}
          @input=${e=>{this.q=e.target.value,this.kb=0}}
          @keydown=${t=>this.onKey(t,e)} />
        <div class="keys meta" aria-hidden="true"><span class="kbd">↑</span><span class="kbd">↓</span> <span class="kbd">Enter</span> <span class="kbd">Esc</span></div>
      </div>
      <div class="list" role="listbox">
        ${e.length?t.map(([e,t])=>t.length?O`<div class="group">${e} <span class="n">${t.length}</span></div>
                    ${t.map(e=>this.item(e,n++))}`:k):O`<div class="blank"><span>${N(`No runs match`)}</span></div>`}
      </div>`}counts(e){let t=e.tasks,n=[N(M`${t.done} of ${t.total} tasks done`)];t.failed&&n.push(Si(`failed`,t.failed)),t.not_started&&n.push(Si(`not_started`,t.not_started)),t.running&&n.push(Si(`running`,t.running)),t.waiting&&n.push(Si(`waiting`,t.waiting));let r=uo(e);r!=null&&n.push(N(M`took ${F(r)}`)),e.cost_usd!==null&&e.cost_usd!==void 0&&n.push(En(e.cost_usd));let i=so(e.quota??[]);return i&&n.push(i),I(...n)}item(e,t){let n=Hi(e.running,e.tasks);return O`<div class=${`item${e.run===this.current?` cur`:``}${t===this.kb?` kb`:``}`} role="option" aria-selected=${e.run===this.current} @click=${()=>this.pick(e.run)}>
      <span class="dot ${n}" aria-hidden="true"></span><span class="nm">${e.run}</span>
      <span class="when" title=${Sn(e.last_ts,!0)}>${e.running?N(`running`):Cn(e.last_ts)}</span>
      <span class="sub">
        ${e.run_group&&e.run_group!==e.run?O`<span>${N(M`Run group ${e.run_group}`)}</span>`:k}
        <span title=${co(e.quota??[])}>${this.counts(e)}</span>
      </span>
    </div>`}};W([H({attribute:!1})],po.prototype,`runs`,void 0),W([H()],po.prototype,`current`,void 0),W([H({type:Boolean,reflect:!0})],po.prototype,`open`,void 0),W([U()],po.prototype,`q`,void 0),W([U()],po.prototype,`kb`,void 0),W([Xn(`input`)],po.prototype,`input`,void 0),po=W([V(`ca-run-picker`),P()],po);var{I:mo}=Fe,ho=e=>e,go=()=>document.createComment(``),_o=(e,t,n)=>{let r=e._$AA.parentNode,i=t===void 0?e._$AB:t._$AA;if(n===void 0)n=new mo(r.insertBefore(go(),i),r.insertBefore(go(),i),e,e.options);else{let t=n._$AB.nextSibling,a=n._$AM,o=a!==e;if(o){let t;n._$AQ?.(e),n._$AM=e,n._$AP!==void 0&&(t=e._$AU)!==a._$AU&&n._$AP(t)}if(t!==i||o){let e=n._$AA;for(;e!==t;){let t=ho(e).nextSibling;ho(r).insertBefore(e,i),e=t}}}return n},vo=(e,t,n=e)=>(e._$AI(t,n),e),yo={},bo=(e,t=yo)=>e._$AH=t,xo=e=>e._$AH,So=e=>{e._$AR(),e._$AA.remove()},Co=(e,t,n)=>{let r=new Map;for(let i=t;i<=n;i++)r.set(e[i],i);return r},X=cr(class extends lr{constructor(e){if(super(e),e.type!==sr.CHILD)throw Error(`repeat() can only be used in text expressions`)}dt(e,t,n){let r;n===void 0?n=t:t!==void 0&&(r=t);let i=[],a=[],o=0;for(let t of e)i[o]=r?r(t,o):o,a[o]=n(t,o),o++;return{values:a,keys:i}}render(e,t,n){return this.dt(e,t,n).values}update(e,[t,n,r]){let i=xo(e),{values:a,keys:o}=this.dt(t,n,r);if(!Array.isArray(i))return this.ut=o,a;let s=this.ut??=[],c=[],l,u,d=0,f=i.length-1,p=0,m=a.length-1;for(;d<=f&&p<=m;)if(i[d]===null)d++;else if(i[f]===null)f--;else if(s[d]===o[p])c[p]=vo(i[d],a[p]),d++,p++;else if(s[f]===o[m])c[m]=vo(i[f],a[m]),f--,m--;else if(s[d]===o[m])c[m]=vo(i[d],a[m]),_o(e,c[m+1],i[d]),d++,m--;else if(s[f]===o[p])c[p]=vo(i[f],a[p]),_o(e,i[d],i[f]),f--,p++;else if(l===void 0&&(l=Co(o,p,m),u=Co(s,d,f)),l.has(s[d])){if(l.has(s[f])){let t=u.get(o[p]),n=t===void 0?null:i[t];if(n===null){let t=_o(e,i[d]);vo(t,a[p]),c[p]=t}else c[p]=vo(n,a[p]),_o(e,i[d],n),i[t]=null;p++}else So(i[f]),f--}else So(i[d]),d++;for(;p<=m;){let t=_o(e,c[m+1]);vo(t,a[p]),c[p++]=t}for(;d<=f;){let e=i[d++];e!==null&&So(e)}return this.ut=o,bo(e,c),xe}}),wo={done:`✓`,failed:`✕`,attention:`◌`,running:`●`,agent:`✦`},To=5200,Eo=class extends A{constructor(...e){super(...e),this.toasts=[],this.next=0}static{this.styles=[B,c`
      :host { position: fixed; right: 18px; bottom: 18px; display: flex; flex-direction: column; gap: 8px; z-index: 60; pointer-events: none; }
      .toast { pointer-events: auto; min-width: 240px; max-width: 380px; padding: 10px 14px; border-radius: 11px;
        background: var(--panel2); border: 1px solid var(--line2); box-shadow: 0 18px 40px color-mix(in srgb, var(--shadow) 60%, transparent);
        display: flex; gap: 10px; align-items: flex-start; animation: toast-in 0.35s var(--ease) both; }
      .toast.out { animation: toast-out 0.35s var(--ease) both; }
      .ti { font-size: 16px; line-height: 1.2; }
      b { display: block; font-size: 12.5px; }
      span.sub { font-size: 11.5px; color: var(--text-muted); }
      .ti { color: var(--text-muted); }
      .done .ti { color: var(--status-done); }
      .failed { border-color: color-mix(in srgb, var(--status-failed) 50%, var(--line2)); }
      .failed .ti { color: var(--status-failed); }
      .attention { border-color: color-mix(in srgb, var(--status-attention) 50%, var(--line2)); }
      .attention .ti { color: var(--status-attention); }
      .running .ti { color: var(--status-running); }
      .agent .ti { color: var(--agent); }
    `]}show(e,t,n=``){let r={id:this.next++,kind:e,title:t,sub:n,out:!1};this.toasts=[...this.toasts,r].slice(-4),setTimeout(()=>{this.toasts=this.toasts.map(e=>e.id===r.id?{...e,out:!0}:e),setTimeout(()=>this.toasts=this.toasts.filter(e=>e.id!==r.id),400)},To)}render(){return O`<div aria-live="polite" style="display:contents">
      ${X(this.toasts,e=>e.id,e=>O`<div class="toast ${e.kind} ${e.out?`out`:``}">
          <span class="ti" aria-hidden="true">${wo[e.kind]}</span>
          <div><b>${e.title}</b>${e.sub?O`<span class="sub">${e.sub}</span>`:k}</div>
        </div>`)}
    </div>`}};W([U()],Eo.prototype,`toasts`,void 0),Eo=W([V(`ca-toasts`)],Eo);function Do(e){return e===`system`?N(`System`):e===`high-contrast`?N(`High contrast`):Ke[e].label}var Oo=e=>{let t=Ke[e].tokens;return O`<span class="sw" style="background:${t.card};border-color:${t.line2}"
    ><i style="background:${t.accent}"></i><i style="background:${t[`code-string`]}"></i><i style="background:${t[`code-keyword`]}"></i
  ></span>`},ko=class extends A{constructor(...e){super(...e),this.value=`contraagent-dark`,this.system=`contraagent-dark`,this.open=!1,this.onDocDown=e=>{this.open&&!e.composedPath().includes(this)&&(this.open=!1)}}static{this.styles=[B,c`
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
    `]}connectedCallback(){super.connectedCallback(),document.addEventListener(`pointerdown`,this.onDocDown)}disconnectedCallback(){super.disconnectedCallback(),document.removeEventListener(`pointerdown`,this.onDocDown)}items(){return[...this.renderRoot.querySelectorAll(`.item`)]}updated(e){e.has(`open`)&&this.open&&(this.items().find(e=>e.getAttribute(`aria-checked`)===`true`)??this.items()[0])?.focus()}close(e){this.open=!1,e&&this.trig?.focus()}choose(e){this.value=e,j(this,`ca-choose-theme`,{theme:e}),this.close(!0)}onTrigKey(e){(e.key===`ArrowDown`||e.key===`ArrowUp`)&&(e.preventDefault(),this.open=!0)}onMenuKey(e){let t=this.items(),n=t.indexOf(e.composedPath()[0]),r=e=>t[(e+t.length)%t.length]?.focus();if(e.key===`ArrowDown`)r(n+1);else if(e.key===`ArrowUp`)r(n-1);else if(e.key===`Home`)r(0);else if(e.key===`End`)r(t.length-1);else if(e.key===`Escape`)this.close(!0);else if(e.key===`Tab`){this.open=!1;return}else return;e.preventDefault(),e.stopPropagation()}item(e){let t=e===this.value,n=e===`system`?O`<span class="sw split" style="border-color:${Ke[`contraagent-dark`].tokens.line2}"
            ><span style="background:${Ke[`contraagent-dark`].tokens.card}"><i style="background:${Ke[`contraagent-dark`].tokens.accent}"></i></span
            ><span style="background:${Ke[`contraagent-light`].tokens.card}"><i style="background:${Ke[`contraagent-light`].tokens.accent}"></i></span
          ></span>`:Oo(e);return O`<button type="button" class="item" role="menuitemradio" aria-checked=${t?`true`:`false`} tabindex="-1"
      data-theme=${e} @click=${()=>this.choose(e)}>
      ${n}<span>${Do(e)}${e===`system`?O`<span class="meta sub">${Ke[this.system].label}</span>`:k}</span><span class="rd" aria-hidden="true"></span>
    </button>`}render(){let e=Ve.filter(e=>e===`system`||!He.includes(e));return O`<button type="button" class="trig" aria-haspopup="menu" aria-expanded=${this.open?`true`:`false`} aria-controls="menu"
        title=${N(M`Theme: ${Do(this.value)}`)} @click=${()=>this.open=!this.open} @keydown=${e=>this.onTrigKey(e)}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" stroke-width="1.5" /><path d="M8 1.75a6.25 6.25 0 0 1 0 12.5z" fill="currentColor" /></svg>
        ${N(`Theme`)}
      </button>
      ${this.open?O`<div id="menu" class="menu" role="menu" aria-label=${N(`Theme`)} @keydown=${e=>this.onMenuKey(e)}>
            ${e.map(e=>this.item(e))}
            <div role="separator"></div>
            <div role="group" aria-labelledby="grp-editor">
              <div class="grp" id="grp-editor">${N(`Editor themes`)}</div>
              ${He.map(e=>this.item(e))}
            </div>
          </div>`:k}`}};W([H()],ko.prototype,`value`,void 0),W([H()],ko.prototype,`system`,void 0),W([U()],ko.prototype,`open`,void 0),W([Xn(`.trig`)],ko.prototype,`trig`,void 0),ko=W([V(`ca-theme-switch`),P()],ko);function Ao(e){switch(e){case`valid`:return N(`passed`);case`invalid`:return N(`failed checks`);case`refused`:return N(`not written (task not started)`);case`failed`:return N(`not written (task failed)`);case`running`:return N(`not written yet (task running)`);case`pending`:return N(`not written yet (task waiting)`)}}function jo(e){switch(e){case`refused`:return N(`The task did not start because an input was missing or failed checks`);case`valid`:return N(`The file passed its checks`);case`invalid`:return N(`The file failed its checks`);case`failed`:return N(`The task failed before it wrote a file that passes its checks`);case`running`:return N(`The task is running`);case`pending`:return N(`The task is waiting`)}}var Mo=()=>N(`Correction: another round in the same agent session after the output failed checks`);function No(e,t){let n=(e??1)-1;return n<1?``:N(t?n===1?`after 1 correction`:M`after ${n} corrections`:n===1?`1 correction`:M`${n} corrections`)}var Po=(e,t,n=``)=>O`<span class="fk ${e?`ok`:`bad`}" title=${n||k}><span aria-hidden="true">${e?`✓`:`✕`}</span> ${t}</span>`;function Fo(e){let t=!!e.file.exists,n=t?N(`found`):e.required?N(`missing (required)`):N(`missing (optional)`);return O`<span class="ct-chip ${t?`valid`:e.required?`invalid`:`pending`}">${n}</span>`}var Io=[`valid`,`invalid`,`refused`,`failed`,`running`,`pending`];Object.defineProperties({},Object.fromEntries(Io.map(e=>[e,{enumerable:!0,get:()=>Ao(e)}]))),Object.defineProperties({},Object.fromEntries(Io.map(e=>[e,{enumerable:!0,get:()=>jo(e)}])));var Lo=e=>e===`invalid`?`invalid_output`:e===`refused`?`invalid_input`:`error`;function Ro(e,t){return e.startsWith(`list[`)||e===`array`?Array.isArray(t):e===`string`?typeof t==`string`:e===`integer`?Number.isInteger(t):e===`number`?typeof t==`number`:e===`boolean`?typeof t==`boolean`:e!==`object`||typeof t==`object`&&!!t&&!Array.isArray(t)}var zo=(e,t)=>e.length>t?`${e.slice(0,t)}…`:e;function Bo(e){if(e===void 0)return O`<span class="jdim">—</span>`;if(typeof e==`string`)return O`<span class="js" title=${e}>"${zo(e,90)}"</span>`;if(Array.isArray(e)){let t=e.slice(0,3).map(e=>typeof e==`string`?`"${zo(e,28)}"`:JSON.stringify(e)).join(`, `);return O`<span class="jn">${e.length===1?N(`1 item`):N(M`${e.length} items`)}</span>
      <span class="jdim">${t}${e.length>3?`, …`:``}</span>`}return typeof e==`object`&&e?O`<span class="jn">${N(`object`)}</span> <span class="jdim">${Object.keys(e).slice(0,4).join(`, `)}</span>`:O`<span class="jn">${JSON.stringify(e)}</span>`}function Vo(e){let t=e.content;return typeof t==`object`&&t?O`<ca-json-tree .value=${t}></ca-json-tree>`:O`<pre class="jtree">${typeof t==`string`?t:N(`Not JSON`)}</pre>`}var Ho=e=>/^RootModel\[(.+)\]$/.exec(e)?.[1]??null;function Uo(e){let t=e.file,n=t.content;if(!e.fields.length&&(e.schema_name===`text`||Ho(e.schema_name)!==null))return t.exists?O`<details class="ct-raw">
          <summary>${Wo(t)}</summary>
          ${Vo(t)}
        </details>`:O``;if(!t.exists)return e.fields.length?O`<table class="ct-check">
          <tr><th>${N(`Field`)}</th><th>${N(`Expected`)}</th></tr>
          ${e.fields.map(e=>O`<tr>
              <td class="jmono">${e.name}</td>
              <td class="jmono jdim">${e.type}${e.required?k:O` <i>${N(`optional`)}</i>`}</td>
            </tr>`)}
        </table>`:O``;let r=typeof n==`object`&&n&&!Array.isArray(n)?n:null,i=e.fields.map(e=>{let t=O``,n;if(r){let i=e.name in r;n=i?r[e.name]:void 0,t=i?Ro(e.type,n)?Po(!0,N(`passed`)):Po(!1,N(`wrong type`),N(M`Expected ${e.type}`)):e.required?Po(!1,N(`missing`),N(`A required field that is not in the file`)):O`<span class="fk none">${N(`absent (optional)`)}</span>`}return O`<tr>
      <td class="jmono">${e.name}</td>
      <td class="jmono jdim">${e.type}${e.required?k:O` <i>${N(`optional`)}</i>`}</td>
      <td>${Bo(n)}</td>
      <td>${t}</td>
    </tr>`}),a=r?Object.keys(r).filter(t=>!e.fields.some(e=>e.name===t)):[];return O`<table class="ct-check">
      <tr><th>${N(`Field`)}</th><th>${N(`Expected`)}</th><th>${N(`In the file`)}</th><th>${N(`Check`)}</th></tr>
      ${i}
      ${a.map(e=>O`<tr>
          <td class="jmono">${e}</td><td class="jdim">${N(`not in the schema`)}</td><td>${Bo(r?.[e])}</td>
          <td><span class="fk warn" title=${N(`Not in the schema`)}>${N(`extra field`)}</span></td>
        </tr>`)}
    </table>
    ${r?k:O`<div class="meta note">${N(`Not a JSON object`)}</div>`}
    <details class="ct-raw">
      <summary>${Wo(t)}</summary>
      ${Vo(t)}
    </details>`}var Wo=e=>I(N(`Whole file`),`${e.size??0} B`,e.mtime?N(M`written ${Sn(e.mtime,!0)}`):``,e.truncated?N(`truncated`):``);function Go(e){let t=Ho(e.schema_name),n=e.schema_name===`text`||t===`str`?N(`text`):t??e.schema_name;return O`<b class="jmono" title=${e.schema_ref||e.schema_name}>${n}</b>`}function Ko(e){let t=e.schema_ref||e.schema_name;if(e.schema_name===`text`)return N(`text file`);let n=Ho(e.schema_name);return n===`str`?O`<span title=${t}>${N(`text (JSON string)`)}</span>`:n?O`<span title=${t}>${N(M`JSON value of type ${n}`)}</span>`:N(O`JSON object, schema ${Go(e)}`)}function qo(e){let t=e.validators??[];if(!t.length)return null;let n=(e.errors??[]).join(`
`),r=t=>e.status===`valid`?Po(!0,N(`passed`)):n.includes(t)?Po(!1,N(`failed checks`)):k;return O`${t.map((e,t)=>O`${t?`, `:``}<span class="jmono">${e}</span> ${r(e)}`)}`}function Jo(e,t,n){let r=e.errors??[],i=Fi(`invalid input: ${r.map(e=>e.replace(/^invalid input:\s*/,``)).join(`; `)}`)[0];if(!i)return r[0]?wn(J(r[0],t)):N(`An input was missing or failed checks`);let a=n?.(i.path);return wn(Ii(J(i.path,t),i.problem,a))}function Yo(e,t){let n=Ko(e),r=qo(e);return O`<dl class="conds">
    ${(t===`output`?[[N(`Format`),n],...r?[[N(`Other checks`),r,N(`Checks beyond the schema (validators)`)]]:[],[N(`Must be written during the task`),e.fresh?N(`yes`):N(`no`),e.fresh?N(`A file from before the task does not count`):N(`A file from before the task counts`)]]:[[N(`Format`),n],...r?[[N(`Other checks`),r,N(`Checks beyond the schema (validators)`)]]:[],[N(`Check time`),N(`when the task starts`)],[N(`Required`),e.required?N(`yes`):N(`no`)]]).map(([e,t,n])=>O`<dt>${e}</dt><dd title=${n??``}>${t}</dd>`)}
  </dl>`}function Xo(e,t,n=``,r={}){let i=t===`output`?O`<span class="ct-chip ${e.status??``}" title=${e.status?jo(e.status):``}>${e.status?Ao(e.status):`—`}</span>${(e.rounds??0)>1?O` <span class="meta" title=${Mo()}>${No(e.rounds,e.status===`valid`)}</span>`:k}`:Fo(e),a=O`<div class="io-hd">${r.chip??i}<span class="jmono ct-path" title=${e.path}>${J(e.path,n)}</span></div>${r.origin?O`<div class="meta io-from">${r.origin}</div>`:k}`;if(t===`output`&&e.status===`refused`)return O`<div class="io-card one">${a}<div class="meta">${Jo(e,n,r.producerOf)}</div></div>`;if(t===`output`&&e.status===`failed`&&!e.file.exists)return O`<div class="io-card one">${a}</div>`;let o=e.errors??[];return O`<div class="io-card">
    ${a}
    ${Yo(e,t)}
    ${Uo(e)}
    ${o.length?O`<h4>${N(`Errors`)}</h4><pre class="ct-err">${o.map(e=>J(e,n)).join(`
`)}</pre>`:k}
  </div>`}var Zo=c`
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
`,Qo=class extends A{constructor(...e){super(...e),this.procs=null}static{this.styles=[B,c`
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
    `]}render(){let e=this.procs?.tree[0];return e?O`<div class="ptree2">${this.node(e,0)}</div>`:O`<div class="meta">${N(`No running processes`)}</div>`}node(e,t){let n=e.full_cmd||e.cmd||``,r=(e.cmd||n).split(` `).slice(0,3).join(` `);return O`<div class="pt-n ${/\b(claude|omp)\b/.test(n)?`llm`:``} ${t?``:`root`}" style="--d:${t}" title=${n}>
        <span class="pt-pid">${e.pid}</span>
        <span class="pt-cmd">${e.key?O`<b>${L(e)}</b> `:k}${r.length>70?`${r.slice(0,70)}…`:r}</span>
        <ca-elapsed class="pt-age" .since=${rr.at(`p:${e.pid}`,e.age_s)}></ca-elapsed>
      </div>
      ${(e.children??[]).map(e=>this.node(e,t+1))}`}};W([H({attribute:!1})],Qo.prototype,`procs`,void 0),Qo=W([V(`ca-proc-tree`),P()],Qo);function $o(e){return e?O`${e.split(` | `).map((e,t)=>O`${t?` | `:``}<span class="f">${e}</span>`)}`:k}function es(e){let t=!1,n=!1,r=!1;for(let i of e){if(i.outcome!==`not_started`)continue;let e=i.attempts[i.attempts.length-1],a=e?.stop===`invalid_input`?Fi(e.reason):[];a.some(e=>e.problem===`missing`)&&(t=!0),a.some(e=>e.problem===`checks`)&&(n=!0),!a.length&&i.cause&&(r=!0)}return I(r?N(`Earlier task failed`):``,t?N(`Input missing`):``,n?N(`Input failed checks`):``)}var ts={failed:`mk-failed`,attention:`mk-pending`};function ns(e){return O`${e.filter(e=>e.text).map((e,t)=>O`${t?` | `:``}<span class="f ${e.tone?`t-${e.tone}`:``}">${e.text}</span>`)}`}var rs=()=>globalThis.matchMedia?.(`(prefers-reduced-motion: reduce)`).matches??!1,is=class extends A{constructor(...e){super(...e),this.journal=[],this.plan={nodes:[],groups:[]},this.prev=new Map,this.changed=[]}static{this.styles=[B,c`
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
      .kpi.failed { --edge: var(--status-failed); }
      .kpi.failed .v, .kpi.failed .k::before { color: var(--status-failed); }
      .kpi.attention { --edge: var(--status-attention); }
      .kpi.attention .v, .kpi.attention .k::before { color: var(--status-attention); }
    `]}history(e){return()=>j(this,`ca-navigate`,{tab:`journal`,stop:e})}show(e,t,n){let r=e.length===1?e[0]:void 0,i=r?this.journal.find(e=>e.key===r):void 0;return r?{label:i?L(i):r,run:()=>j(this,`ca-open-task`,{key:r})}:{label:n,run:this.history(t)}}tiles(){let e=Xa(this.journal),t=Qr(this.journal,this.plan),n=ei(t),r=[{text:Si(`done`,n.done+n.recovered),tone:``},{text:n.failed?Si(`failed`,n.failed):``,tone:Vi(n.failed,`failed`)},{text:n.not_started?Si(`not_started`,n.not_started):``,tone:Vi(n.not_started,`attention`)}];return[{id:`tasks`,tone:``,label:N(`Tasks`),value:n.total,sub:``,parts:r},{id:`attempts`,tone:``,label:N(`Attempts`),value:e.attempts,sub:I(e.launches===1?N(`1 agent session`):N(M`${e.launches} agent sessions`),e.python===1?N(`1 Python task attempt`):N(M`${e.python} Python task attempts`)),tip:N(`Attempts that ran, retries included (journal.jsonl)`)},...this.spendTiles(),{id:`bad`,tone:Vi(e.bad,`failed`),label:N(`Failed attempts`),value:e.bad,sub:e.bad?``:N(`All attempts passed`),...e.bad?{action:{label:N(`Failed attempts in history`),run:this.history(`bad`)}}:{}},{id:`notstarted`,tone:Vi(n.not_started,`attention`),label:N(`Not started`),value:n.not_started,sub:n.not_started?es(t.values()):N(`All tasks started`),...n.not_started?{action:{label:N(`Not-started tasks in history`),run:this.history(`invalid_input`)}}:{}},{id:`wall`,tone:``,label:N(`Agent session time`),value:F(e.launchWall),sub:N(M`Python tasks: ${F(e.pythonWall)}`),tip:N(`Sum over all agent sessions, including ones running at once`)},{id:`retry`,tone:``,label:N(`Retries`),value:e.retries,sub:e.retries?e.retriedTasks===1?N(`1 task retried`):N(M`${e.retriedTasks} tasks retried`):N(`No retries`),tip:N(`Attempts after a failed attempt, each in a new agent session (RetryingRunner)`),...e.retries?{action:this.show(e.retriedKeys,`retried`,N(`Retried tasks in history`))}:{}},{id:`ct`,tone:``,label:N(`Corrections`),value:e.fixups,sub:e.fixups?e.fixupTasks===1?N(`1 task with corrections`):N(M`${e.fixupTasks} tasks with corrections`):N(`No corrections`),tip:N(`More rounds in the same agent session after the output failed checks (rounds)`),...e.fixups?{action:this.show(e.fixupKeys,`fixup`,N(`Attempts with corrections in history`))}:{}},{id:`fo`,tone:``,label:N(`Model switches`),value:e.switches,sub:e.switches?e.switchTasks===1?N(`1 task with model switches`):N(M`${e.switchTasks} tasks with model switches`):N(`No model switches`),tip:N(`To the next model after a failure such as a rate limit, an error or a timeout (Router hops)`)}]}spendTiles(){let e=ci(this.journal);if(!e)return[];let t=di(this.journal)[0];return[{id:`cost`,tone:``,label:N(`Cost`),value:En(e.cost),sub:t&&t.share!==null?[N(M`Highest cost: ${t.kind}`),I(En(t.spend.cost),N(M`${Math.round(t.share*100)}% of the total`))]:``,tip:N(`Reported by the coding agent`)},{id:`tokens`,tone:``,label:N(`Tokens`),value:z(oi(e)),sub:I(N(M`${z(e.input)} input`),N(M`${z(e.output)} output`),N(M`${z(e.cache_read+e.cache_creation)} cache`)),tip:I(N(M`${z(e.cache_read)} cache read`),N(M`${z(e.cache_creation)} cache write`),e.calls===1?N(`1 API call`):N(M`${e.calls} API calls`))}]}render(){let e=this.tiles();this.changed=[];for(let t of e)typeof t.value==`number`&&((this.prev.get(t.id)??0)!==t.value&&this.changed.push(t.id),this.prev.set(t.id,t.value));return O`<div class="kpis">${e.map(e=>this.tile(e))}</div>`}tile(e){return O`<div class="kpi ${e.tone}" data-id=${e.id} title=${e.tip??k}>
      <div class="k words ${ts[e.tone]??``}">${e.label}</div>
      <div class="v">${typeof e.value==`number`?O`<ca-count .value=${e.value}></ca-count>`:e.value}</div>
      ${e.parts?O`<div class="s words">${ns(e.parts)}</div>`:(typeof e.sub==`string`?[e.sub]:e.sub).map(e=>O`<div class="s words">${$o(e)}</div>`)}
      ${e.action?O`<div class="a words"><a class="lnk" href="#" @click=${t=>{t.preventDefault(),e.action?.run()}}>${e.action.label}</a></div>`:k}
    </div>`}updated(){if(!rs())for(let e of this.changed)this.renderRoot.querySelector(`.kpi[data-id="${e}"]`)?.animate([{transform:`scale(1)`},{transform:`scale(1.04)`,boxShadow:`0 0 0 1px var(--line2)`,offset:.35},{transform:`scale(1)`}],{duration:700,easing:`cubic-bezier(.2,.8,.2,1)`})}};W([H({attribute:!1})],is.prototype,`journal`,void 0),W([H({attribute:!1})],is.prototype,`plan`,void 0),is=W([V(`ca-kpis`),P()],is);var as=[`input`,`cache_read`,`cache_creation`,`output`],os=class extends A{constructor(...e){super(...e),this.journal=[],this.top=5}static{this.styles=[B,c`
      :host { display: block; }
      .kinds { display: grid; grid-template-columns: minmax(90px, max-content) minmax(0, 1fr) max-content max-content; gap: 8px 14px; align-items: center; }
      .kind { font-family: var(--mono); font-size: 12px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .bar { display: flex; height: 12px; border-radius: 4px; overflow: hidden; background: var(--track); }
      .bar i { display: block; height: 100%; }
      .num { font-variant-numeric: tabular-nums; text-align: right; font-size: 12px; white-space: nowrap; }
      .share { color: var(--text-muted); min-width: 3.5em; }
      .p-input { background: var(--tok-input); }
      .p-cache_read { background: var(--tok-cache-read); }
      .p-cache_creation { background: var(--tok-cache-write); }
      .p-output { background: var(--tok-output); }
      .legend { margin-top: 10px; }
      h4 { margin: 16px 0 6px; font-size: 12px; color: var(--text-2); font-weight: 600; }
      .top { display: grid; grid-template-columns: minmax(160px, max-content) 64px 64px 40px; column-gap: 24px; row-gap: 4px; align-items: baseline; }
      .top a { font-family: var(--mono); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    `]}partLabel(e){switch(e){case`input`:return N(`input`);case`cache_read`:return N(`cache read`);case`cache_creation`:return N(`cache write`);case`output`:return N(`output`)}}bar(e,t){let n=oi(e),r=t?100*n/t:0;return O`<div class="bar" title=${I(...as.map(t=>`${this.partLabel(t)} ${z(e[t])}`))} style="width:${Math.max(r,.5).toFixed(2)}%">
      ${as.map(t=>e[t]&&n?O`<i class="p-${t}" style="width:${(100*e[t]/n).toFixed(2)}%"></i>`:k)}
    </div>`}render(){if(!ci(this.journal))return O`<div class="meta">${N(`No tokens reported`)}</div>`;let e=di(this.journal),t=Math.max(1,...e.map(e=>oi(e.spend))),n=ui(this.journal).slice(0,this.top);return O`<div class="kinds">
        ${X(e,e=>e.id,e=>O`<span class="kind" title=${e.id}>${e.id}</span>${this.bar(e.spend,t)}
            <span class="num">${I(z(oi(e.spend)),En(e.spend.cost))}</span>
            <span class="num share">${e.share===null?``:`${Math.round(e.share*100)}%`}</span>`)}
      </div>
      <div class="legend">${as.map(e=>O`<span><i class="p-${e}"></i>${this.partLabel(e)}</span>`)}</div>
      <h4>${N(`Most expensive tasks`)}</h4>
      <div class="top">
        ${n.map(e=>O`<a class="lnk" href="#" title=${e.id} @click=${t=>{t.preventDefault(),j(this,`ca-open-task`,{key:e.id})}}>${L(e)}</a>
            <span class="num">${z(oi(e.spend))}</span>
            <span class="num">${En(e.spend.cost)}</span>
            <span class="num share">${e.share===null?``:N(M`${Math.round(e.share*100)}%`)}</span>`)}
      </div>`}};W([H({attribute:!1})],os.prototype,`journal`,void 0),W([H({type:Number})],os.prototype,`top`,void 0),os=W([V(`ca-spend-breakdown`),P()],os);var ss=class extends A{static{this.styles=[B,c`
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
    `]}constructor(){super(),this.journal=[],new nr(this)}row(e,t,n,r){let i=n[`${e}_pct`],a=r[`${e}_pct`];if(i==null&&a==null)return k;let o=Math.max(0,Math.min(100,i??a??0)),s=Math.max(o,Math.min(100,a??o)),c=r[`${e}_resets_at`],l=s>=100?`full`:s>=80?`hot`:``;return O`<span class="name">${t}</span>
      <span class="bar ${l}" title=${`${to(i)} → ${to(a)}`}>
        <i class="before" style="width:${o}%"></i>
        <i class="during" style="left:${o}%;width:${s-o}%"></i>
      </span>
      <span class="val ${l}">${to(i)} → <b>${to(a)}</b></span>
      <span class="reset" title=${c?Sn(c,!0):``}>${ro(c)}</span>`}render(){let e=hi(this.journal);return e.length?O`${e.map(e=>{let t=no(e.last.status);return O`<div class="acct">
        <div class="acct-h"><i>${N(`Identity`)}</i><b>${ji(e.credential)||`—`}</b>${t?O`<span class="pill p-near" title=${e.last.status??``}>${t}</span>`:k}</div>
        <div class="rows">
          ${this.row(`seven_day`,N(`Weekly usage`),e.first,e.last)} ${this.row(`five_hour`,N(`5-hour usage`),e.first,e.last)}
        </div>
      </div>`})}`:k}};W([H({attribute:!1})],ss.prototype,`journal`,void 0),ss=W([V(`ca-quota`),P()],ss);var cs=cr(class extends lr{constructor(){super(...arguments),this.key=k}render(e,t){return this.key=e,t}update(e,[t,n]){return t!==this.key&&(bo(e),this.key=t),n}}),ls=14,us=(e,t,n)=>n<t?t:Math.min(n,Math.max(t,e));function ds(e,t){let n=Math.max(e.left,t.left),r=Math.max(e.top,t.top),i=Math.min(e.left+e.width,t.left+t.width),a=Math.min(e.top+e.height,t.top+t.height);return i>n&&a>r?{left:n,top:r,width:i-n,height:a-r}:null}function fs(e,t,n,r=e){let i=ds(r,t);if(!i)return{shown:!1,x:0,y:0,side:`right`,arrow:0,fits:!1};let{width:a,height:o}=n,s=t.left+8,c=t.top+8,l=t.left+t.width-8,u=t.top+t.height-8,d=e.left+e.width,f=e.top+e.height,p=i.top+i.height/2,m=i.left+i.width/2,h=us(p-o/2,c,u-o),g=us(m-a/2,s,l-a),_={right:l-(d+12)-a,left:e.left-12-a-s,below:u-(f+12)-o,above:e.top-12-o-c},v=[`right`,`left`,`below`,`above`],y=v.find(e=>_[e]>=0)??v.reduce((e,t)=>_[t]>_[e]?t:e),b,x;switch(y){case`right`:[b,x]=[us(d+12,s,l-a),h];break;case`left`:[b,x]=[us(e.left-12-a,s,l-a),h];break;case`below`:[b,x]=[g,us(f+12,c,u-o)];break;case`above`:[b,x]=[g,us(e.top-12-o,c,u-o)]}let S=y===`right`||y===`left`?us(p-x,ls,o-ls):us(m-b,ls,a-ls);return{shown:!0,x:b,y:x,side:y,arrow:S,fits:_[y]>=0}}var ps=[`done`,`running`,`pending`,`failed`,`blocked`,`skipped`],ms=640,hs=.7,gs=360,_s=2.5,vs=4,ys=24,bs=150,xs=30,Ss=8,Cs=(e=14)=>O`<svg class="ic loop-ic" width=${e} height=${e} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
    <path d="M12.7,9.71 A5,5 0 1 1 11.21,4.17" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"></path>
    <path d="M12.44,5.2 L9.15,5.06 L11.73,2 z" fill="currentColor"></path>
  </svg>`,ws=()=>O`<svg class="ic in-ic" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
    <rect x="3.4" y="0.7" width="7.9" height="7.9" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.2"></rect>
    <path d="M0.7,3.6 V9.7 Q0.7,11.3 2.3,11.3 H8.4" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"></path>
  </svg>`,Ts=e=>O`<span class="k-ic ${e?``:`llm`}" aria-hidden="true">${e?`⚙`:`✦`}</span>`,Es=e=>[...e.units,...e.single];function Ds(e,t){let n=Es(e),r=e.units.length?Ra(t):Ra(n.length);return{cols:Math.min(r.cols,Math.max(1,n.length)),size:r.size,gap:r.size>=10?4:2}}var Z=class extends A{constructor(...e){super(...e),this.plan={nodes:[],groups:[]},this.journal=[],this.run=``,this.live=!1,this.layer=``,this.unit=``,this.sel=``,this.hover=null,this.asTable=!1,this.down=!1,this.lay=null,this.view={k:1,x:0,y:0},this.frameH=0,this.sort=`order`,this.scrollRow=0,this.missing=``,this.pressed=!1,this.cardRoom=0,this.announced=``,this.replacing=!1,this.auto=[],this.segments=[],this.graph={path:[],nodes:[],layers:[],boxes:[],edges:[],stubs:[],units:[],slots:{},routes:[],order:{layers:[],boxes:{}}},this.matrix=null,this.orders=new Map,this.byKey=new Map,this.waiters=new Map,this.active=new Map,this.cell=null,this.refocus=!1,this.cameFrom=``,this.layKey=``,this.layPath=``,this.fitK=1,this.moved=!1,this.pan=null,this.swallowClick=!1,this.quiet=!1,this.onTabToCard=e=>{if(e.key!==`Tab`||e.shiftKey||e.defaultPrevented)return;let t=this.anchorFocus(),n=this.renderRoot instanceof ShadowRoot?this.renderRoot.activeElement:null;if(!t||n!==t)return;let r=this.renderRoot.querySelector(`.insp button`);r&&(e.preventDefault(),r.focus())},this.onEscape=e=>{if(e.key!==`Escape`||e.defaultPrevented)return;if(this.sel){e.preventDefault(),this.select(``);return}let t=Ma(this.segments,this.auto);t&&(e.preventDefault(),this.refocus=!0,this.cameFrom=this.segments[this.segments.length-1]??``,this.go(t))},this.onWheel=e=>{if(this.asTable||this.matrix||!(e.ctrlKey||e.metaKey))return;let t=this.renderRoot.querySelector(`.frame`);if(!t)return;e.preventDefault();let n=t.getBoundingClientRect();this.zoomBy(Math.exp(-e.deltaY*.0015),e.clientX-n.left,e.clientY-n.top)},this.onClickCapture=e=>{this.swallowClick&&(this.swallowClick=!1,e.stopPropagation(),e.preventDefault())}}static{this.styles=[B,c`
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
      /* Graph | Table: the pressed one is raised, as the header's language switch. */
      .views { display: inline-flex; margin-left: 6px; border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
      .tools .views button { height: 20px; line-height: 20px; padding: 0 10px; border: 0; border-radius: 0; color: var(--text-muted); }
      .tools .views button + button { border-left: 1px solid var(--line); }
      .tools .views button[aria-pressed='true'] { background: var(--raise); color: var(--text); cursor: default; }
      .tools .views button:focus-visible { outline-offset: -2px; }

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
      .mx { overflow: auto; max-width: 100%; max-height: max(${gs}px, ${hs*100}vh); border-radius: 6px; border: 1px solid var(--line); }
      table.matrix { border-collapse: separate; border-spacing: 0; font-size: 11px; width: 100%; min-width: max-content; }
      .matrix th, .matrix td { padding: 0 6px; height: ${ys}px; border-bottom: 1px solid var(--line); white-space: nowrap; }
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
    `]}willUpdate(e){if(e.has(`run`)&&this.orders.clear(),e.has(`layer`)&&e.get(`layer`)!==void 0){this.moved=!1,this.active.clear(),this.cell=null,this.scrollRow=0;let e=this.renderRoot instanceof ShadowRoot?this.renderRoot.activeElement:null;this.refocus=e!==null&&!e.closest(`.views`),this.replacing?this.replacing=!1:this.missing=``}if(e.has(`run`)&&e.get(`run`)!==void 0&&(this.missing=``),!e.has(`plan`)&&!e.has(`layer`)&&!e.has(`run`)&&!e.has(`down`))return;if(this.auto=ka(this.plan),this.segments=this.layer?this.layer.split(`/`):this.auto,this.layer&&this.plan.nodes.length){let e=ja(this.plan,this.segments);e?e.join(`/`)!==this.layer&&(this.segments=e,this.setLayer(e.join(`/`)===this.auto.join(`/`)?``:e.join(`/`))):(this.missing=this.layer,this.segments=this.auto,this.setLayer(``))}let{path:t,loop:n}=Aa(this.segments),r=t.join(`/`);if(this.graph=Oa(this.plan,t,this.orders.get(r),this.down),this.orders.set(r,this.graph.order),this.matrix=n?Na(this.plan,t,n,this.graph.order):null,e.has(`plan`)){this.byKey=new Map(this.plan.nodes.map(e=>[e.key,e])),this.waiters=new Map;for(let e of this.plan.nodes)for(let t of e.after??[])(this.waiters.get(t)??this.waiters.set(t,[]).get(t))?.push(e.key)}}disconnectedCallback(){super.disconnectedCallback(),this.removeEventListener(`wheel`,this.onWheel),this.removeEventListener(`click`,this.onClickCapture,{capture:!0}),this.removeEventListener(`keydown`,this.onEscape),this.removeEventListener(`keydown`,this.onTabToCard),this.resize?.disconnect(),this.resize=void 0}connectedCallback(){super.connectedCallback(),this.addEventListener(`wheel`,this.onWheel,{passive:!1}),this.addEventListener(`click`,this.onClickCapture,{capture:!0}),this.addEventListener(`keydown`,this.onEscape),this.addEventListener(`keydown`,this.onTabToCard)}updated(e){this.resize||(this.resize=new ResizeObserver(()=>{this.fit(),this.anchorCard()}),this.resize.observe(this)),this.place(),(this.refocus||this.cameFrom)&&this.restoreFocus(),this.anchorCard(),e.has(`sel`)&&this.selectionChanged()}anchor(){let e=this.renderRoot.querySelector(`.main > .frame`),t=e?.querySelector(`tr.sel > th`);if(e&&t)return{item:t,clear:t,frame:e};let n=e?.querySelector(`.mark.sel, .taskchip.sel, .node.sel, .box.sel`);if(!e||!n)return null;let r=n.classList.contains(`box`)?n.querySelector(`:scope > .hd`)??n:n;return{item:r,clear:r.closest(`.node`)??n,frame:e}}anchorCard(){let e=this.renderRoot.querySelector(`.insp`),t=e&&!this.down?e.querySelector(`.scroll`).scrollHeight+24+16:0;if(t!==this.cardRoom&&(t>this.frameH||this.cardRoom>0)&&(this.cardRoom=t,this.matrix?this.requestUpdate():this.fit()),!e||this.down)return;let n=this.anchor(),r=this.renderRoot.querySelector(`.main`);if(!n||!r){e.classList.remove(`placed`);return}let i=r.getBoundingClientRect(),a=e=>({left:e.left-i.left,top:e.top-i.top,width:e.width,height:e.height}),o=a(n.item.getBoundingClientRect()),s=a(n.clear.getBoundingClientRect()),c=a(n.frame.getBoundingClientRect()),l=n.frame.querySelector(`.mx`),u=fs(o,l?a(l.getBoundingClientRect()):c,{width:0,height:0}).shown,d=e.querySelector(`.scroll`);d&&(d.style.maxHeight=`${Math.max(120,c.height-16-24)}px`);let f={width:e.offsetWidth,height:e.offsetHeight},p=fs(s,c,f,o);!p.fits&&n.clear!==n.item&&!n.clear.classList.contains(`node`)&&(p=fs(o,c,f)),e.classList.toggle(`placed`,p.shown&&u),e.dataset.side=p.side,e.style.left=`${p.x}px`,e.style.top=`${p.y}px`,e.style.setProperty(`--arrow`,`${p.arrow}px`)}anchorFocus(){let e=this.anchor();return e?e.item.matches(`button`)?e.item:e.item.querySelector(`.name`):null}selectionChanged(){for(let e of this.renderRoot.querySelectorAll(`[aria-describedby="insp"]`))e.removeAttribute(`aria-describedby`);this.anchorFocus()?.setAttribute(`aria-describedby`,`insp`);let e=this.renderRoot.querySelector(`.insp`),t=e?.querySelector(`h4`)?.textContent?.trim()??``,n=e?.querySelector(`[data-status]`)?.textContent?.trim()??``,r=t?I(t,n):``;r!==this.announced&&(this.announced=r),this.down&&this.whenReleased(()=>this.revealOverSheet())}whenReleased(e){if(!this.pressed)return e();globalThis.addEventListener(`pointerup`,()=>setTimeout(e),{once:!0})}revealOverSheet(){let e=this.anchor()?.item;if(!e)return;let t=e.getBoundingClientRect(),n=this.renderRoot.querySelector(`.insp`)?.getBoundingClientRect(),r=Math.min(globalThis.innerHeight,n?.top??1/0);(t.top<0||t.bottom>r)&&e.scrollIntoView({block:`center`})}onCardKey(e){let t=[...e.currentTarget.querySelectorAll(`button`)],n=this.renderRoot instanceof ShadowRoot?this.renderRoot.activeElement:null;if(e.key===`Tab`&&e.shiftKey&&n===t[0]){let t=this.anchorFocus();if(!t)return;e.preventDefault(),this.quiet=!0,t.focus(),this.quiet=!1}else e.key===`Escape`&&(this.quiet=!0,this.anchorFocus()?.focus(),this.quiet=!1)}place(){let e=this.renderRoot.querySelector(`.dag`);if(!e)return;let t=new Map;for(let n of e.querySelectorAll(`[data-id]`))t.set(n.dataset.id??``,{w:n.offsetWidth,h:n.offsetHeight});let n=this.graph,r=JSON.stringify([n.path,n.slots,n.routes.map(e=>e.steps.map(e=>e.id)),this.down,[...t]]);if(r===this.layKey)return this.fit();this.layKey=r,this.layPath=n.path.join(`/`),this.lay=Ga(n,t,this.down),this.updateComplete.then(()=>this.fit())}restoreFocus(){let e=this.cameFrom;this.refocus=!1,this.cameFrom=``;let t=this.renderRoot,n=null;if(e.startsWith(`loop:`))n=t.querySelector(`.box[data-box="${CSS.escape(e)}"] > .hd .name`);else if(e){let r=this.graph.nodes.find(t=>t.type===`flow`&&t.name===e);r&&(n=t.querySelector(`.node[data-id="${CSS.escape(r.id)}"] [tabindex="0"]`))}this.quiet=!0,(n??t.querySelector(`.mark[tabindex="0"], .node .name, .crumbs button`))?.focus(),this.quiet=!1}focusSelect(e){this.quiet||this.select(e)}setLayer(e){this.replacing=!0,j(this,`ca-navigate`,{layer:e,unit:this.unit,sel:this.sel,replace:!0})}go(e,t=this.unit){let n=this.auto.join(`/`),r=e.join(`/`);j(this,`ca-navigate`,{layer:r===n?``:r,unit:t})}chosen(){return La(this.graph,this.matrix,this.sel)}select(e){e!==this.sel&&j(this,`ca-navigate`,{sel:e})}primary(e){if(e.type===`mark`)return this.open(e.mark);if(e.type===`box`)return this.go([...this.segments,e.box.id]);if(e.node.type===`flow`)return this.go([...this.graph.path,e.node.name]);this.tasksOf(e.node)}tasksOf(e){j(this,`ca-navigate`,{tab:`tasks`,kind:e.kinds.length===1?e.kinds[0]:``})}onItemClick(e,t){e.target.closest(`.mark, .taskchip, .node, .box`)===e.currentTarget&&(e.stopPropagation(),!(e.detail>=2)&&this.select(t))}onItemDblClick(e,t){if(e.target.closest(`.mark, .taskchip, .node, .box`)!==e.currentTarget)return;e.stopPropagation();let n=La(this.graph,this.matrix,t);n&&this.primary(n)}onNameKey(e,t){if(e.key!==`Enter`)return;e.preventDefault();let n=La(this.graph,this.matrix,t);n&&this.primary(n)}crumbs(){let e=this.segments,t=this.unit;if(!e.length&&!t)return k;let{path:n,loop:r}=Aa(e),i=[...n.map((e,t)=>({name:aa(e),tip:e,to:n.slice(0,t+1)})),...(r?r.slice(Zi.length).split(`.`):[]).map((e,t,r)=>{let i=Zi+r.slice(0,t+1).join(`.`),a=this.graph.boxes.find(e=>e.id===i)?.file||this.matrix?.box.file||``,o=/^\d+$/.test(e);return{name:N(o?M`Loop at ${this.where(e,a)}`:`Loop`),tip:o&&a?`${a}:${e}`:``,to:[...n,i]}})];return O`<div class="bar">
      ${e.length?O`<nav aria-label=${N(`Pipeline layer`)}>
            <ol class="crumbs">
              <li><button type="button" @click=${()=>this.go([])}>${N(`Pipeline`)}</button></li>
              ${i.map((e,t)=>O`<li><span class="sep" aria-hidden="true">›</span>
                  ${t===i.length-1?O`<span aria-current="page" title=${e.tip||k}>${e.name}</span>`:O`<button type="button" title=${e.tip||k} @click=${()=>this.go(e.to)}>${e.name}</button>`}</li>`)}
            </ol>
          </nav>`:k}
      ${t?O`<span class="pin">${N(M`Unit: ${t}`)}
            <button type="button" class="switch" @click=${()=>j(this,`ca-navigate`,{unit:``})}>${N(`Clear highlight`)}</button></span>`:k}
    </div>`}fit(){let e=this.clientWidth,t=e>0&&e<ms;t!==this.down&&(this.down=t);let n=this.lay;if(!n||this.matrix)return;let r=this.renderRoot.querySelector(`.frame`)?.clientWidth||e,i=Ja(n.w,n.h,r,t?1/0:Math.max(gs,hs*window.innerHeight));this.fitK=i.k;let a=t?i.h:Math.max(i.h,this.cardRoom),o=i.y;this.moved?a>this.frameH&&(this.frameH=a):(a!==this.frameH&&(this.frameH=a),(i.k!==this.view.k||i.x!==this.view.x||o!==this.view.y)&&(this.view={k:i.k,x:i.x,y:o}))}zoomTools(){let e=!this.moved&&this.fitK>=1;return O`<button type="button" aria-label=${N(`Zoom out`)} title=${N(`Zoom out (Ctrl + scroll)`)} @click=${()=>this.zoomBy(1/1.25)}>−</button>
      <button type="button" aria-label=${N(`Zoom in`)} title=${N(`Zoom in (Ctrl + scroll)`)} @click=${()=>this.zoomBy(1.25)}>+</button>
      <button type="button" ?disabled=${e} @click=${()=>this.showAll()}>${N(`Show all`)}</button>`}showAll(){this.moved=!1,this.fit(),this.requestUpdate()}zoomBy(e,t=(this.renderRoot.querySelector(`.frame`)?.clientWidth??this.clientWidth)/2,n=this.frameH/2){this.moved=!0,this.view=Ya(this.view,e,t,n,Math.min(1,this.fitK)/2,_s)}onPointerDown(e){this.pressed=!0,globalThis.addEventListener(`pointerup`,()=>this.pressed=!1,{once:!0}),!(e.button!==0||e.target.closest(`.tools`)||this.down&&e.pointerType!==`mouse`)&&(this.pan={id:e.pointerId,px:e.clientX,py:e.clientY,x:this.view.x,y:this.view.y,far:!1})}onPointerMove(e){let t=this.pan;if(!t||t.id!==e.pointerId)return;let n=e.clientX-t.px,r=e.clientY-t.py;!t.far&&Math.hypot(n,r)<vs||(t.far||(t.far=!0,e.currentTarget.setPointerCapture(e.pointerId),e.currentTarget.classList.add(`drag`)),this.moved=!0,this.view={...this.view,x:t.x+n,y:t.y+r})}onPointerUp(e){let t=this.pan;t&&t.id===e.pointerId&&(this.pan=null,e.currentTarget.classList.remove(`drag`),t.far&&(this.swallowClick=!0))}reveal(e){let t=this.renderRoot.querySelector(`.frame`);if(!t)return;let n=t.getBoundingClientRect(),r=e.getBoundingClientRect(),i=0,a=0;r.left<n.left+24?i=n.left+24-r.left:r.right>n.right-24&&(i=n.right-24-r.right),r.top<n.top+24?a=n.top+24-r.top:r.bottom>n.bottom-24&&(a=n.bottom-24-r.bottom),(i||a)&&(this.moved=!0,this.view={...this.view,x:this.view.x+i,y:this.view.y+a})}get hl(){let e=this.hover===null?this.chosen():null,t=e?.type===`mark`?e.mark.unit||e.mark.key:null;return this.hover??t??(this.unit||null)}lit(){let e=this.hl;if(e===null)return null;let t=this.plan.nodes.filter(t=>t.unit?t.unit===e:t.key===e).map(e=>e.key),n=new Set(t),r=e=>{let r=new Set(t),i=[...t];for(let t=i.pop();t!==void 0;t=i.pop())for(let a of e(t))r.has(a)||(r.add(a),n.add(a),i.push(a))};return r(e=>this.waiters.get(e)??[]),r(e=>this.byKey.get(e)?.after??[]),n}render(){if(!this.plan.nodes.length)return O`<div class="blank" style="padding:24px">${this.live?N(`No tasks scheduled yet`):N(`No tasks scheduled`)}</div>`;let e=Qr(this.journal,this.plan),t=t=>{let n=e.get(t);return n?Li(n,e,this.run):``},n=this.matrix,r=!!n||this.asTable,i=n?this.matrixView(n,t):this.asTable?this.table():this.dag(t);return O`${this.crumbs()}${this.missingLine()}
      <div class="main">${i}${this.inspector(t)}</div>
      <div class="foot">
        ${this.legend()}
        <div class="tools">${r?k:this.zoomTools()}${this.viewSwitch(r)}</div>
        <div class="keys">${this.keyHints().map((e,t)=>O`${t?` | `:``}<span>${e}</span>`)}</div>
      </div>`}viewSwitch(e){return O`<div class="views" role="group" aria-label=${N(`View`)}>
      <button type="button" aria-pressed=${!e} @click=${()=>this.showGraph()}>${N(`Graph`)}</button>
      <button type="button" aria-pressed=${e} @click=${()=>this.showTable()}>${N(`Table`)}</button>
    </div>`}showGraph(){if(this.asTable=!1,!this.matrix)return;let e=this.segments[this.segments.length-1]??``,t=Ma(this.segments,this.auto)??[],n=this.auto.join(`/`);j(this,`ca-navigate`,{layer:t.join(`/`)===n?``:t.join(`/`),unit:this.unit,sel:e})}showTable(){this.matrix||(this.asTable=!0)}missingLine(){if(!this.missing)return k;let e=this.missing.split(`/`),t=e[e.length-1]||this.missing;return O`<div class="missing" role="status" title=${this.missing}>${N(O`No layer <code>${t}</code> in this run`)}</div>`}keyHints(){let e=this.sel?N(`Esc: clear selection`):Ma(this.segments,this.auto)?N(`Esc: up a level`):``;return(this.matrix?[N(`Arrow keys: marks`),N(`Enter: open`),e]:this.asTable?[N(`Tab: next row`),N(`Enter: open`),e]:[N(`Tab: next node`),N(`Arrow keys: marks`),N(`Shift + arrow keys: earlier and later tasks`),N(`Enter: open`),e]).filter(Boolean)}dag(e){let t=this.graphView(e),n=this.view;return O`<div class="frame gframe ${this.down?`down`:``}" style="height:${Math.round(this.frameH)}px"
        @pointerdown=${e=>this.onPointerDown(e)} @pointermove=${e=>this.onPointerMove(e)}
        @pointerup=${e=>this.onPointerUp(e)} @pointercancel=${e=>this.onPointerUp(e)}
        @click=${e=>!e.target.closest(`.node, .box, .stub, .tools`)&&this.select(``)}>
        <div class="stage view" style="transform:translate(${n.x}px,${n.y}px) scale(${n.k})">${t}</div>
      </div>`}at(e,t){let n=this.lay?.at[e];if(!n)return`left:0;top:0`;let r=t?t.x+1:0,i=t?t.y+1:0;return`left:${n.x-r}px;top:${n.y-i}px`}graphView(e){let t=this.lit(),n=this.graph,r=this.lay,i=new Map(n.nodes.map(e=>[e.id,e])),a=new Map(n.boxes.map(e=>[e.id,e])),o=new Map(n.stubs.map(e=>[e.id,e])),s=e=>(n.slots[e]??[]).flat().filter(e=>!Y(e)),c=(n,r)=>{let s=a.get(n);if(s)return this.box(s,r,(e,t)=>c(e,t));let l=o.get(n);if(l)return O`<span class="stub" data-id=${l.id} style=${this.at(l.id,r)} title=${N(`Outside this layer`)}>${l.label}</span>`;let u=i.get(n);return u?this.node(u,r,e,t):k},l=!!r&&n.nodes.every(e=>r.at[e.id]),u=r?.w??0,d=r?.h??0;return O`<div class="dag ${this.down?`down`:``} ${t?`hl`:``} ${l?``:`unplaced`}" style="width:${u}px;height:${d}px"
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
        ${(r?.edges??[]).map(e=>be`<path class=${e.type} d=${qa(e.runs,r?.down)} marker-end="url(#arr)"></path>`)}
        ${(r?.returns??[]).map(e=>be`<path class="ret" data-box=${e.box} d=${Ka(e,r?.down)} marker-end="url(#arr-ret)"></path>`)}
      </svg>
      ${X(s(``),e=>e,e=>c(e,null))}
    </div>`}box(e,t,n){let r=this.lay?.at[e.id]??null,i=N(M`Loop at ${this.where(e.loop,e.file)}`),a=e.spread.length>1?Oi(e.spread):``,o=(this.graph.slots[e.id]??[]).flat().filter(e=>!Y(e)),s=r?`;width:${r.w}px;height:${r.h}px`:``;return O`<section class="box ${this.sel===e.id?`sel`:``}" role="group" data-box=${e.id} style=${this.at(e.id,t)+s}
        aria-label=${I(i,Ei(e.passes),a)}
        @click=${t=>this.onItemClick(t,e.id)} @dblclick=${t=>this.onItemDblClick(t,e.id)}>
      <div class="hd" data-id=${`lbl:${e.id}`}>
        <span class="line">
          <button type="button" class="name" title=${I(ki(),i)} aria-pressed=${this.sel===e.id}
            @focus=${()=>this.focusSelect(e.id)} @keydown=${t=>this.onNameKey(t,e.id)}>${Cs()}${ki()}</button>
          <span class="count">${Ei(e.passes)}</span>
        </span>
        ${a?O`<span class="spread" title=${N(`Units by number of passes`)}>${a}</span>`:k}
      </div>
      <span class="cue" aria-hidden="true">${ws()}</span>
      <div class="in">${X(o,e=>e,e=>n(e,r))}</div>
    </section>`}node(e,t,n,r){let i=e.counts,a=i.done+i.skipped,o=i.failed||e.errors?`fail`:i.running?`cur`:a===i.total?`done`:``,s=za(e),c=s?{id:e.id,label:e.label,slots:Es(e).filter(e=>e?.state===`failed`),grid:{cols:Ss,size:12,gap:4}}:{id:e.id,label:e.label,slots:Es(e),grid:Ds(e,this.graph.units.length)},l=this.exceptions(e),u=this.sel===e.id,d=e.type===`flow`?I(N(M`Function ${e.name}`),this.doneOf(i)):I(e.label,this.executorWord(e),this.doneOf(i)),f=e.executor===`mixed`?O`${Ts(!1)}${Ts(!0)}`:e.executor?Ts(e.executor===`python`):k;return O`<section class="node ${e.type} ${e.executor===`agent`?`agent`:``} ${o} ${u?`sel`:``}" role="group" data-id=${e.id}
      aria-label=${this.nodeLabel(e)}
      style="${this.at(e.id,t)};--cols:${c.grid.cols};--m:${c.grid.size}px;--g:${c.grid.gap}px"
      @click=${t=>this.onItemClick(t,e.id)} @dblclick=${t=>this.onItemDblClick(t,e.id)}>
      <div class="hd">
        <span class="nm">${f}<button type="button" class="name" title=${d} aria-pressed=${u}
          @focus=${()=>this.focusSelect(e.id)} @keydown=${t=>this.onNameKey(t,e.id)}>${e.label}</button></span>
        <span class="right"><span class="count" aria-hidden="true" title=${this.doneOf(i)}>${a}/${i.total}</span>${e.type===`flow`?O`<span class="cue" aria-hidden="true">${ws()}</span>`:k}</span>
      </div>
      ${s?this.statusBar(e,c,n,r):this.marks(c,n,r)}
      ${l.length?O`<div class="ex" aria-hidden="true">${l.map(([e,t])=>O`<span class=${e}>${t}</span>`)}</div>`:k}
    </section>`}executorWord(e){return e.executor===`agent`?N(`Agent task`):e.executor===`python`?N(`Python task`):e.executor===`mixed`?I(N(`Agent task`),N(`Python task`)):``}statusBar(e,t,n,r){let i=Ba(e.counts,ps),a=t.slots.slice(0,Ss),o=t.slots.length-a.length,s=Math.min(this.active.get(t.id)??0,Math.max(0,a.length-1));return O`<div class="sbar" role="img" aria-label=${this.stateCounts(e.counts)}>
        ${i.map(e=>O`<i class=${e.state} style="width:${e.pct}%" title=${this.countOf(e.state,e.n)}></i>`)}
      </div>
      ${a.length?O`<div class="fails" @keydown=${e=>this.onKey(e,{...t,slots:a,grid:{...t.grid,cols:a.length}})}>
            ${a.map((e,i)=>e?this.mark(t,e,i,i===s,n,r,!0):k)}
            ${o>0?O`<span>${N(M`+${o}`)}</span>`:k}
          </div>`:k}`}marks(e,t,n){let r=Math.min(this.active.get(e.id)??Os(e.slots),e.slots.length-1);return O`<div class="marks ${e.grid.size>=10?`big`:``}" @keydown=${t=>this.onKey(t,e)}>
      ${e.slots.map((i,a)=>i?this.mark(e,i,a,a===r,t,n):O`<span class="slot"></span>`)}
    </div>`}markText(e,t,n,r=``){let i=t.flow?void 0:this.byKey.get(t.key),a=L({kind:e,unit:t.unit}),o=!t.flow&&t.state===`blocked`?n(t.key):``,s=o?N(M`Not started: ${o}`):this.stateWord(t.state),c=i?.attempts??1,l=c>1?N(M`${c} attempts`):``,u=t.passes?Di(t.passes):``,d=t.flow||t.count>1?N(M`${t.count} tasks`):``,f=t.counts?this.notDone(t.counts):[],p=t.error===void 0?[]:[N(`Flow call stopped with an error`),t.error],m=!t.flow&&(t.state===`done`||t.state===`failed`)&&i?.wall_s?F(i.wall_s):``;return{name:a,parts:[s,r,u,l,d,...f,...p,m].filter(Boolean),id:t.flow?N(M`Flow call ${t.key}`):t.key}}open(e){if(e.flow)return this.go([...this.graph.path,e.flow],e.unit||this.unit);let t=this.byKey.get(e.key);j(this,`ca-open-task`,e.state===`blocked`?{key:e.key,view:`input`}:t?.executor===`python`?{key:e.key,view:`output`}:{key:e.key})}mark(e,t,n,r,i,a,o=!1){let{name:s,parts:c}=this.markText(e.label,t,i),l=t.unit||t.key,u=a!==null&&(t.unit!==``&&t.unit===this.hl||t.keys.some(e=>a.has(e))),d=Ia(e.id,t),f=this.sel===d?`sel`:``,p=t=>{this.hover=l,this.active.set(e.id,n),this.reveal(t.currentTarget),this.focusSelect(d)},m=[s,c[0]??``].filter(Boolean).join(`
`);return o?O`<button type="button" class="taskchip ${u?`on`:``} ${f}" data-i=${n} tabindex=${r?0:-1}
        title=${m} aria-label=${I(s,...c)} aria-pressed=${!!f}
        @mouseenter=${()=>this.hover=l} @focus=${p} @blur=${()=>this.hover=null}
        @click=${()=>this.select(d)} @dblclick=${()=>this.open(t)}>${t.unit||t.key}</button>`:O`<button type="button" class="mark ${t.state} ${u?`on`:``} ${f}" data-i=${n} data-n=${t.passes??k} tabindex=${r?0:-1}
      title=${m}
      aria-label=${I(s,...c)} aria-pressed=${!!f}
      @mouseenter=${()=>this.hover=l}
      @focus=${p}
      @blur=${()=>this.hover=null}
      @click=${()=>this.select(d)}
      @dblclick=${()=>this.open(t)}></button>`}matrixView(e,t){let n=Pa(e.rows,this.sort),r=e.columns,i=this.hl,a=r.map((e,t)=>{let n=r[t-1]?.passes;if(!n)return-1;let i=e.passes.findIndex((e,t)=>e!==n[t]);return i<0?e.passes.length===n.length?-1:Math.min(e.passes.length,n.length):i}),o=e=>a[e]===0?`g0`:(a[e]??-1)>0?`g1`:``,s=e.head.length,c=n.length>bs,l=c?Math.max(0,this.scrollRow-xs):0,u=c?Math.min(n.length,this.scrollRow+60+20):n.length,d=this.cell&&this.cell[0]<n.length?this.cell:this.firstCell(n),f=e.rows.filter(e=>e.unit).length,p=e=>e===0||a[e]===0?`g0`:(a[e]??-1)>0?`g1`:``,m=(t,n,r)=>{let i=`top:${r*22}px`;return t.type===`pass`?O`<th scope="colgroup" colspan=${t.span} class="pass ${p(n)}" style=${i}
          title=${t.box.id===e.box.id?N(M`Loop at ${this.where(t.box.loop,t.box.file)}`):N(M`Nested loop at ${this.where(t.box.loop,t.box.file)}`)}>${Ti(t.pass)}</th>`:t.type===`loop`?O`<th scope="colgroup" colspan=${t.span} class="loop ${p(n)}" style=${i}
          title=${N(M`Nested loop at ${this.where(t.box.loop,t.box.file)}`)}>${ki()}</th>`:O`<th scope="col" rowspan=${t.rows} class="nh ${p(n)}" style=${i}
        title=${t.node.type===`flow`?N(M`Function ${t.node.name}`):I(t.node.label,this.executorWord(t.node))}
        aria-label=${t.node.type===`flow`?t.node.label:I(t.node.label,this.executorWord(t.node))}>${t.node.executor&&t.node.executor!==`mixed`?Ts(t.node.executor===`python`):k}${t.node.label}</th>`},h=t=>{let n=[],r=0;for(let i of e.head[t]??[]){for(;ks(e.head,t,r);)r++;n.push(r),r+=i.span}return n},g=[Ei(e.box.passes),e.box.spread.length>1?Oi(e.box.spread):``,N(f===1?`1 unit`:M`${f} units`)].filter(Boolean),_=this.down?0:Math.round(Math.max(this.frameH,this.cardRoom));return O`<div class="frame mxframe" style=${_?`min-height:${_}px`:``}><div class="mxblock view">
      <div class="mxbar">
        <span class="cap" title=${e.box.file?`${e.box.file}:${e.box.loop}`:k}>${N(M`Loop at ${this.where(e.box.loop,e.box.file)}`)}</span>
        <label>${N(`Sort units`)}
          <select @change=${e=>this.sort=e.target.value}>
            <option value="order" ?selected=${this.sort===`order`}>${N(`Scheduled order`)}</option>
            <option value="passes" ?selected=${this.sort===`passes`}>${N(`Number of passes`)}</option>
            <option value="state" ?selected=${this.sort===`state`}>${N(`Status`)}</option>
          </select>
        </label>
        <span class="sum">${g.map((e,t)=>O`${t?O`<span class="sep"> | </span>`:k}<span class="f">${e}</span>`)}</span>
      </div>
      <div class="mx ${i?`hl`:``}" @scroll=${e=>this.onMatrixScroll(e)} @mouseleave=${()=>this.hover=null}>
        <table class="matrix big" role="grid" aria-rowcount=${n.length+s} aria-colcount=${r.length+2}
          aria-label=${I(N(M`Loop at ${this.where(e.box.loop,e.box.file)}`),Ei(e.box.passes))}>
          <thead>
            ${e.head.map((e,t)=>{let n=h(t);return O`<tr>
                ${t===0?O`<th scope="col" rowspan=${s} class="uh" style="top:0">${N(`Unit`)}</th>
                      <th scope="col" rowspan=${s} class="pn" style="top:0" title=${N(`Passes of this loop`)}>${N(`Passes`)}</th>`:k}
                ${e.map((e,r)=>m(e,n[r]??0,t))}
              </tr>`})}
          </thead>
          <tbody @keydown=${e=>this.onMatrixKey(e,n)}>
            ${l>0?O`<tr class="gap" aria-hidden="true"><td colspan=${r.length+2} style="height:${l*ys}px"></td></tr>`:k}
            ${X(n.slice(l,u),e=>e.unit,(e,n)=>{let a=l+n;return O`<tr class=${e.unit&&e.unit===i?`on`:``} aria-rowindex=${a+s+1}>
                  ${e.unit?O`<th scope="row" title=${e.unit}>${e.unit}</th>`:O`<th scope="row" class="none" title=${N(`Tasks that run once per run, not once per unit`)}>${N(`No unit`)}</th>`}
                  <td class="pn ${e.passes>1?`many`:``}">${e.passes}</td>
                  ${e.cells.map((n,i)=>{let s=r[i],c=!!n&&d!==null&&d[0]===a&&d[1]===i;return O`<td class="c ${o(i)}" role="gridcell">${n&&s?this.cellMark(e,n,a,i,s.node,s.passes,c,t):k}</td>`})}
                </tr>`})}
            ${u<n.length?O`<tr class="gap" aria-hidden="true"><td colspan=${r.length+2} style="height:${(n.length-u)*ys}px"></td></tr>`:k}
          </tbody>
        </table>
      </div>
    </div></div>`}cellMark(e,t,n,r,i,a,o,s){let{name:c,parts:l}=this.markText(i.label,t,s,a.map(Ti).join(`, `)),u=t.unit||t.key,d=Ia(i.id,t,a),f=this.sel===d;return O`<button type="button" class="mark ${t.state} ${e.unit&&e.unit===this.hl?`on`:``} ${f?`sel`:``}" data-r=${n} data-c=${r} tabindex=${o?0:-1}
      title=${[c,l[0]??``].filter(Boolean).join(`
`)} aria-label=${I(c,...l)} aria-pressed=${f}
      @mouseenter=${()=>this.hover=u}
      @focus=${()=>{this.hover=u,this.cell=[n,r],this.focusSelect(d)}}
      @blur=${()=>this.hover=null}
      @click=${()=>this.select(d)}
      @dblclick=${()=>this.open(t)}></button>`}firstCell(e){for(let t=0;t<e.length;t++){let n=e[t]?.cells.findIndex(e=>e!==null)??-1;if(n>=0)return[t,n]}return null}onMatrixScroll(e){let t=Math.floor(e.currentTarget.scrollTop/ys);Math.abs(t-this.scrollRow)>=xs/2&&(this.scrollRow=t),this.anchorCard()}onMatrixKey(e,t){let n=e.target;if(!n.classList.contains(`mark`))return;let r=Number(n.dataset.r),i=Number(n.dataset.c);if(e.key===`Enter`){let n=t[r]?.cells[i];e.preventDefault(),n&&this.open(n);return}let a=Fa(t.map(e=>e.cells.map(e=>e!==null)),r,i,e.key,e.ctrlKey||e.metaKey);if(!a)return;e.preventDefault(),this.cell=a;let o=this.renderRoot.querySelector(`.mx`);if(o&&t.length>bs){let e=a[0]*ys;(e<o.scrollTop+48||e>o.scrollTop+o.clientHeight-72)&&(o.scrollTop=Math.max(0,e-o.clientHeight/2)),this.scrollRow=Math.floor(o.scrollTop/ys)}this.requestUpdate(),this.updateComplete.then(()=>this.renderRoot.querySelector(`.matrix .mark[data-r="${a[0]}"][data-c="${a[1]}"]`)?.focus())}stateCounts(e){return I(...ps.filter(t=>e[t]).map(t=>this.countOf(t,e[t])))}doneOf(e){return N(M`${e.done+e.skipped} of ${e.total} tasks done`)}notDone(e){return[`failed`,`blocked`,`running`,`pending`].filter(t=>e[t]).map(t=>this.countOf(t,e[t]))}stateWord(e){return e===`pending`&&!this.live?N(`not run`):xi(e)}where(e,t){let n=t?t.slice(t.lastIndexOf(`/`)+1):``;return n?`${n}:${e}`:N(M`line ${e}`)}countOf(e,t){switch(e){case`blocked`:return Si(`not_started`,t);case`pending`:return Si(this.live?`waiting`:`not_run`,t);default:return Si(e,t)}}exceptions(e){let t=e.counts,n=[];return t.failed&&n.push([`err`,this.countOf(`failed`,t.failed)]),e.errors&&n.push([`err`,e.errors===1?N(`1 flow call stopped with an error`):N(M`${e.errors} flow calls stopped with an error`)]),t.blocked&&n.push([`warn`,this.countOf(`blocked`,t.blocked)]),t.running&&n.push([`live`,this.countOf(`running`,t.running)]),t.pending&&n.push([`mut`,this.countOf(`pending`,t.pending)]),n}neighbours(e){let t=this.graph,n=e=>{let n=t.nodes.find(t=>t.id===e);return n?n.box?N(M`${n.label} in the loop`):n.label:e},r=r=>[...t.stubs.filter(t=>t.to===e.id&&t.type===r).map(e=>e.label),...t.edges.filter(t=>t.to===e.id&&t.type===r).map(e=>n(e.from))];return{waits:r(`after`),after:r(`created`),feeds:[...new Set(t.edges.filter(t=>t.from===e.id).map(e=>n(e.to)))]}}nodeLabel(e){let t=e.counts,{waits:n,after:r,feeds:i}=this.neighbours(e);return[e.type===`flow`?I(N(M`Function ${e.label}`),this.doneOf(t)):I(e.label,this.executorWord(e),this.doneOf(t)),...this.exceptions(e).map(([,e])=>e),n.length?N(M`Waits for ${n.join(`, `)}`):``,r.length?N(M`Created after ${r.join(`, `)}`):``,i.length?N(M`Later tasks: ${i.join(`, `)}`):``].filter(Boolean).join(`. `)}onKey(e,t){let n=e.target;if(!n.classList.contains(`mark`)&&!n.classList.contains(`taskchip`))return;if(e.shiftKey&&e.key.startsWith(`Arrow`))return this.alongEdge(e,t);let{slots:r}=t;if(e.key===`Enter`){let t=r[Number(n.dataset.i)];e.preventDefault(),t&&this.open(t);return}let i=this.active.get(t.id)??Os(r),a={ArrowRight:1,ArrowLeft:-1,ArrowDown:t.grid.cols,ArrowUp:-t.grid.cols},o;if(e.key===`Home`)o=Os(r);else if(e.key===`End`)o=r.length-1-[...r].reverse().findIndex(e=>e!==null);else if(a[e.key]!==void 0){let t=a[e.key];for(o=i+t;o>=0&&o<r.length&&!r[o];)o+=Math.sign(t);if(o<0||o>=r.length)return}else return;e.preventDefault(),this.active.set(t.id,o),this.requestUpdate();let s=e.currentTarget;this.updateComplete.then(()=>s.querySelector(`[data-i="${o}"]`)?.focus())}alongEdge(e,t){let n=e.key===`ArrowRight`||e.key===`ArrowDown`?`later`:`earlier`,r=this.lay,i=Va(this.graph,t.id,n,e=>{let t=r?.at[e];return t?r?.down?t.x+t.w/2:t.y+t.h/2:0});if(e.preventDefault(),!i)return;let a=this.graph.nodes.find(e=>e.id===i);if(!a)return;let o=t.slots[this.active.get(t.id)??Os(t.slots)]?.unit??``,s=za(a)?Es(a).filter(e=>e?.state===`failed`):Es(a),c=o?s.findIndex(e=>e?.unit===o):-1,l=c>=0?c:this.active.get(a.id)??Os(s);this.active.set(a.id,l),this.requestUpdate(),this.updateComplete.then(()=>{let e=this.renderRoot.querySelector(`.node[data-id="${CSS.escape(i)}"]`);(e?.querySelector(`[data-i="${l}"]`)??e?.querySelector(`.name`))?.focus()})}legend(){let e=this.asTable&&!this.matrix,t=(e?[]:this.matrix?this.matrix.rows.flatMap(e=>e.cells):this.graph.nodes.flatMap(e=>za(e)?Es(e).map(e=>e&&{...e,passes:void 0}):Es(e))).filter(e=>e!==null),n=new Set(t.map(e=>e.state)),r=!this.matrix&&t.some(e=>e.passes),i=!this.matrix&&!e&&[...this.graph.edges,...this.graph.stubs].some(e=>e.type===`created`),a=this.matrix?this.matrix.columns.map(e=>e.node):this.graph.nodes,o=new Set(a.flatMap(e=>e.executor===`mixed`?[`agent`,`python`]:e.executor?[e.executor]:[])),s=!this.matrix&&!e&&this.graph.boxes.length>0,c=!this.matrix&&(s||this.graph.nodes.some(e=>e.type===`flow`)),l=e=>be`<svg width="22" height="8" aria-hidden="true"><path d="M1,4 H21" stroke-dasharray=${e?`5 4`:`none`}></path></svg>`;return O`<div class="legend big">
      ${ps.filter(e=>n.has(e)).map(e=>O`<span aria-hidden="true"><i class="mark ${e}"></i>${this.stateWord(e)}</span>`)}
      ${r?O`<span aria-hidden="true"><i class="mark done" data-n="2"></i>${N(`number of passes`)}</span>`:k}
      ${o.has(`agent`)?O`<span>${Ts(!1)}${N(`agent task`)}</span>`:k}
      ${o.has(`python`)?O`<span>${Ts(!0)}${N(`Python task`)}</span>`:k}
      ${i?O`<span>${l(!1)}${N(`waits for output`)}</span><span>${l(!0)}${N(`created after result`)}</span>`:k}
      ${s?O`<span><svg width="24" height="12" aria-hidden="true"><path class="ret" d="M20,1.5 V5.5 Q20,9.5 16,9.5 H8 Q4,9.5 4,5.5 V5"></path>
            <path class="ret-head" d="M4,0.8 L1.4,5 L6.6,5 z"></path></svg>${N(`next pass`)}</span>`:k}
      ${c?O`<span>${ws()}${N(`has an inner view`)}</span>`:k}
    </div>`}inspector(e){let t=this.chosen();return O`${t?cs(this.sel,O`<section id="insp" class="insp ${this.down?`sheet`:``}" aria-label=${N(`Selected item`)}
          @keydown=${e=>this.onCardKey(e)}>
          <span class="ptr" aria-hidden="true"></span>
          <div class="scroll">${this.inspect(t,e)}</div>
        </section>`):k}<div class="sr" role="status">${this.announced}</div>`}inspect(e,t){let n=(e,t)=>O`<dt>${e}</dt><dd>${t}</dd>`,r=(e,t,n=!1)=>O`<button type="button" class="go ${n?`primary`:``}" @click=${t}>${e}</button>`,i=O`<button type="button" class="switch" @click=${()=>this.select(``)}>${N(`Clear selection`)}</button>`,a=e=>e.length?e.join(`, `):N(`none`);if(e.type===`box`){let t=e.box,a=this.where(t.loop,t.file);return O`<h4 title=${t.file?`${t.file}:${t.loop}`:k}>${Cs(16)}${N(M`Loop at ${a}`)}</h4>
        <dl>
          ${n(N(`Passes`),Ei(t.passes))}
          ${t.spread.length>1?n(N(`Units by number of passes`),Oi(t.spread)):k}
        </dl>
        <div class="acts">${r(N(M`Passes of the loop at ${a}`),()=>this.primary(e),!0)}${i}</div>`}if(e.type===`node`){let t=e.node,o=t.counts,{waits:s,after:c,feeds:l}=this.neighbours(t),u=this.exceptions(t).map(([e,t])=>O`<div class=${e}>${t}</div>`);return t.type===`flow`?O`<h4 title=${t.name}>${ws()}${t.label}</h4>
          <div class="sub">${N(`Function`)}</div>
          <dl>
            ${n(N(`Flow calls`),t.calls)}
            ${n(N(`Tasks`),O`${this.doneOf(o)}${u}`)}
            ${n(N(`Waits for`),a(s))}
            ${c.length?n(N(`Created after`),a(c)):k}
            ${n(N(`Later tasks`),a(l))}
          </dl>
          <div class="acts">${r(N(M`Inside ${t.label}`),()=>this.primary(e),!0)}${i}</div>`:O`<h4>${t.executor&&t.executor!==`mixed`?Ts(t.executor===`python`):k}${t.label}</h4>
        <div class="sub">${this.executorWord(t)}</div>
        <dl>
          ${n(N(`Tasks`),O`${this.doneOf(o)}${u}`)}
          ${n(N(`Waits for`),a(s))}
          ${c.length?n(N(`Created after`),a(c)):k}
          ${n(N(`Later tasks`),a(l))}
        </dl>
        <div class="acts">${r(N(M`Tasks of ${t.label}`),()=>this.primary(e),!0)}${i}</div>`}let{node:o,mark:s,passes:c}=e,l=L({kind:o.label,unit:s.unit}),u=!s.flow&&s.state===`blocked`?t(s.key):``,d=O`<span data-status class=${s.state===`failed`?`err`:s.state===`blocked`?`warn`:``}>${this.stateWord(s.state)}</span>`,f=O`<h4 title=${s.flow?N(M`Flow call ${s.key}`):s.key}><i class="mark ${s.state}" aria-hidden="true"></i>${l}</h4>`,p=c.length?c.map(Ti).join(`, `):s.passes?Di(s.passes):``;if(s.flow){let t=s.counts;return O`${f}
        <dl>
          ${n(N(`Status`),d)}
          ${p?n(N(`Pass`),p):k}
          ${t?n(N(`Tasks`),O`${this.doneOf(t)}${this.notDone(t).map(e=>O`<div>${e}</div>`)}`):k}
          ${s.error===void 0?k:n(N(`Error`),O`<span class="err">${s.error||N(`Flow call stopped with an error`)}</span>`)}
        </dl>
        <div class="acts">${r(N(M`Inside ${aa(s.flow)}`),()=>this.primary(e),!0)}${i}</div>`}let m=this.journal.filter(e=>s.keys.includes(e.key)).filter(K),h=m.map(e=>e.cost_usd).filter(e=>typeof e==`number`),g=m.reduce((e,t)=>e+(t.wall_s??0),0);return O`${f}
      <dl>
        ${n(N(`Status`),u?O`${d}<div>${u}</div>`:d)}
        ${p?n(N(`Pass`),p):k}
        ${s.count>1?n(N(`Tasks`),N(M`${s.count} tasks`)):k}
        ${n(N(`Attempts`),m.length||N(`none`))}
        ${n(N(`Time`),m.length?F(g):N(`none`))}
        ${n(N(`Cost`),h.length?En(h.reduce((e,t)=>e+t,0)):`—`)}
      </dl>
      <div class="acts">${r(N(`Task detail`),()=>this.primary(e),!0)}${o.kinds.length===1?r(N(M`Tasks of ${o.label}`),()=>this.tasksOf(o)):k}${i}</div>`}table(){let e=this.graph.nodes,t=e.some(e=>e.type===`flow`),n=[...this.graph.edges,...this.graph.stubs].some(e=>e.type===`created`),r=new Map(this.graph.boxes.map(e=>[e.id,e])),i=e=>e.join(`, `)||N(`none`);return O`<div class="frame tframe" style=${!this.down&&this.layPath===this.graph.path.join(`/`)&&this.frameH>0?`height:${Math.round(this.frameH)}px`:`max-height:max(${gs}px, ${hs*100}vh)`} @scroll=${()=>this.anchorCard()}
        @click=${e=>!e.target.closest(`tbody tr`)&&this.select(``)}>
      <table class="list view">
        <thead>
          <tr>
            <th scope="col" class="fit">${N(t?`Kind or function`:`Kind`)}</th>
            <th scope="col" class="fit">${N(`Status`)}</th>
            <th scope="col">${N(`Waits for`)}</th>
            ${n?O`<th scope="col">${N(`Created after`)}</th>`:k}
            <th scope="col">${N(`Later tasks`)}</th>
          </tr>
        </thead>
        <tbody>
          ${X(e,e=>e.id,e=>{let t=e.counts,{waits:a,after:o,feeds:s}=this.neighbours(e),c=e.box?r.get(e.box):void 0,l=this.sel===e.id,u=e.type===`flow`?I(N(M`Function ${e.name}`),this.doneOf(t)):I(e.label,this.executorWord(e),this.doneOf(t)),d=e.type===`flow`?ws():e.executor&&e.executor!==`mixed`?Ts(e.executor===`python`):e.executor?O`${Ts(!1)}${Ts(!0)}`:k,f=c?N(M`Loop at ${this.where(c.loop,c.file)}`):``;return O`<tr class=${l?`sel`:``} data-id=${e.id}
                @click=${t=>!t.target.closest(`.loopchip`)&&t.detail<2&&this.select(e.id)}
                @dblclick=${t=>!t.target.closest(`.loopchip`)&&this.primary({type:`node`,id:e.id,node:e})}>
              <th scope="row" class="fit">
                <span class="nm">${d}<button type="button" class="name" title=${u} aria-pressed=${l}
                  @focus=${()=>this.focusSelect(e.id)} @keydown=${t=>this.onNameKey(t,e.id)}>${e.label}</button>${c?O`<button type="button" class="taskchip loopchip" title=${I(f,Ei(c.passes))}
                      aria-label=${I(N(M`Passes of the loop at ${this.where(c.loop,c.file)}`),Ei(c.passes))}
                      @click=${()=>this.go([...this.graph.path,c.id])}>${Cs(12)}${Ei(c.passes)}</button>`:k}</span>
              </th>
              <td class="fit st">${this.statusLine(e)}</td>
              <td class="rel">${i(a)}</td>
              ${n?O`<td class="rel">${i(o)}</td>`:k}
              <td class="rel">${i(s)}</td>
            </tr>`})}
        </tbody>
      </table>
    </div>`}statusLine(e){let t=e.counts,n=O`<span class="sep" aria-hidden="true"> | </span>`;return O`<span class="n" aria-hidden="true" title=${this.doneOf(t)}>${t.done+t.skipped}/${t.total}</span><span class="sr">${this.doneOf(t)}</span>${this.exceptions(e).map(([e,t])=>O`${n}<span class=${e}>${t}</span>`)}`}};W([H({attribute:!1})],Z.prototype,`plan`,void 0),W([H({attribute:!1})],Z.prototype,`journal`,void 0),W([H()],Z.prototype,`run`,void 0),W([H({type:Boolean})],Z.prototype,`live`,void 0),W([H()],Z.prototype,`layer`,void 0),W([H()],Z.prototype,`unit`,void 0),W([H()],Z.prototype,`sel`,void 0),W([U()],Z.prototype,`hover`,void 0),W([U()],Z.prototype,`asTable`,void 0),W([U()],Z.prototype,`down`,void 0),W([U()],Z.prototype,`lay`,void 0),W([U()],Z.prototype,`view`,void 0),W([U()],Z.prototype,`frameH`,void 0),W([U()],Z.prototype,`sort`,void 0),W([U()],Z.prototype,`scrollRow`,void 0),W([U()],Z.prototype,`missing`,void 0),W([U()],Z.prototype,`announced`,void 0),Z=W([V(`ca-pipeline-graph`),P()],Z);function Os(e){return Math.max(0,e.findIndex(e=>e!==null))}function ks(e,t,n){for(let r=0;r<t;r++){let i=0;for(let a of e[r]??[]){if(n>=i&&n<i+a.span&&r+a.rows>t)return!0;i+=a.span}}return!1}var As={failed:`✕`,attention:`◌`,done:`✓`,running:``,muted:`■`,"":`■`},js=class extends A{constructor(...e){super(...e),this.procs=null,this.plan={nodes:[],groups:[]}}static{this.styles=[B,c`
      :host { display: block; }
      .drv { display: flex; gap: 14px; align-items: flex-start; }
      .drv-ic { width: 42px; height: 42px; border-radius: 12px; flex: none; display: grid; place-items: center; font-size: 16px;
        background: var(--raise); color: var(--text-muted); }
      .drv.on .drv-ic { background: var(--status-running-bg); box-shadow: 0 0 0 1px color-mix(in srgb, var(--status-running) 35%, transparent), 0 0 22px var(--status-running-bg); }
      /* how a run ended: the mark's shape and the title's words carry it; the colour only where a status applies */
      .drv-ic.failed { background: var(--status-failed-bg); color: var(--status-failed); font-weight: 700; }
      .drv-ic.attention { background: var(--status-attention-bg); color: var(--status-attention); font-weight: 700; }
      .drv-ic.done { color: var(--status-done); font-weight: 700; }
      .drv.on .drv-ic .spin { width: 18px; height: 18px; }
      .drv-t { font-size: 15px; font-weight: 600; }
      .drv-up { font-family: var(--mono); font-size: 12px; color: var(--status-running); margin-left: 6px; font-weight: 400; }
      .drv-cmd { margin-top: 8px; }
      .drv-cmd summary { cursor: pointer; font-size: 11px; color: var(--text-muted); }
      .failed { color: var(--status-failed); }
      .attention { color: var(--status-attention); }
      .drv-cmd code { display: block; margin-top: 4px; white-space: pre-wrap; word-break: break-all; color: var(--text-2); max-height: 120px; overflow: auto; }
    `]}stateTitle(){if(!this.plan.nodes.length)return[N(`Not running`),``];let e=Ki(this.plan);return e.failed?[N(`Finished with errors`),`failed`]:e.left?[e.left===1?N(`Finished with 1 task not done`):N(M`Finished with ${e.left} tasks not done`),`attention`]:e.notStarted?[N(`Finished with errors`),`attention`]:[N(`Finished`),`done`]}render(){let e=this.procs,t=this.summary;if(!e?.alive){let[e,n]=this.stateTitle(),r=qi(t);return O`<div class="drv off">
        <div class="drv-ic ${n}" aria-hidden="true">${As[n]}</div>
        <div>
          <div class="drv-t ${n===`done`?``:n}">${e}</div>
          <div class="meta">${I(t?.last_ts?N(M`Ended ${Sn(t.last_ts,!0)}`):N(`No activity`),r==null?``:N(M`Took ${F(r)}`),t?.run_group?N(M`Run group ${t.run_group}`):``)}</div>
        </div>
      </div>`}let n=Date.parse(e.started_at),r=rr.at(`drv:${e.pid??``}`,Number.isNaN(n)?1:(Date.now()-n)/1e3),i=[[N(`PID`),e.pid??`—`],[N(`Run group`),e.run_group],[N(`Running at once (limit)`),e.max_workers||`—`],[N(`Started`),Sn(e.started_at,!0)]];return O`<div class="drv on">
      <div class="drv-ic"><span class="spin"></span></div>
      <div style="min-width:0">
        <div class="drv-t">${N(`Running`)} <ca-elapsed class="drv-up" .since=${r}></ca-elapsed></div>
        <div class="drv-facts">${i.map(([e,t])=>O`<span><i>${e}</i>${t}</span>`)}</div>
        <details class="drv-cmd"><summary>${N(`Command line`)}</summary><code>${e.argv.join(` `)}</code></details>
      </div>
    </div>`}};W([H({attribute:!1})],js.prototype,`procs`,void 0),W([H({attribute:!1})],js.prototype,`summary`,void 0),W([H({attribute:!1})],js.prototype,`plan`,void 0),js=W([V(`ca-run-driver`),P()],js);var Ms=e=>new Date(e).toLocaleTimeString(mn(),{hour:`2-digit`,minute:`2-digit`,hourCycle:`h23`}),Ns=e=>new Date(e).toLocaleTimeString(mn(),{hour:`2-digit`,minute:`2-digit`,second:`2-digit`,hourCycle:`h23`}),Ps=6e5,Fs=class extends A{constructor(...e){super(...e),this.journal=[],this.procs=null,this.live=!1,this.run=``,this.drawnRun=null,this.timer=null}static{this.styles=[B,c`
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
    `]}updated(e){e.has(`live`)&&this.tick(this.live)}connectedCallback(){super.connectedCallback(),this.tick(this.live)}disconnectedCallback(){super.disconnectedCallback(),this.tick(!1)}tick(e){e&&!this.timer&&(this.timer=setInterval(()=>this.requestUpdate(),1e3)),!e&&this.timer&&(clearInterval(this.timer),this.timer=null)}render(){let e=Date.now(),t=this.live?qr(this.procs).map(t=>({kind:t.kind,cls:t.cls,t0:rr.at(t.id,t.ageS,e)})):[],n=$a(this.journal,t,e);if(!n)return O`<div class="blank" style="padding:28px"><span class="ic" aria-hidden="true">⏱</span>${this.live?N(`No finished attempts yet`):N(`No finished attempts`)}</div>`;let r=this.drawnRun!==this.run;this.drawnRun=this.run;let i=Qr(this.journal,{nodes:[],groups:[]}),a=(e,t)=>{let n=t.row;if(!n)return`${e}\n${N(`running`)}`;if(!K(n)){let e=i.get(n.key),t=n.stop===`invalid_input`&&e?Li(e,i,this.run):``;return[L(n),t?N(M`Not started: ${t}`):q(n.stop,n.reason),n.key].join(`
`)}let r=Pi(n.hops),a=n.reason&&!n.ok?J(n.reason,this.run):``;return[L(n),I(q(n.stop),F(n.wall_s),N(M`ended ${Ns(t.end)}`)),r?N(M`Model switch: ${r}`):n.model?N(M`Model ${n.model}`):``,a,n.key].filter(Boolean).join(`
`)},o=Math.min(1,(e-n.t0)/n.span),s=n.span<Ps?Ns:Ms;return O`<div class="tl ${r?`anim`:``}">
        <div class="tl-axis">${[0,.25,.5,.75,1].map(e=>O`<span>${s(n.t0+n.span*e)}</span>`)}</div>
        ${X(n.lanes,e=>e.name,t=>O`<div class="tl-row">
            <span class="nm" title=${t.name}>${t.name}</span>
            <div class="tl-lane" style="--tracks:${t.tracks}">
              ${t.bars.map(r=>{let i=eo(r,n,e);return O`<span class="tl-bar ${r.cls}" style="--track:${r.track};left:${i.left.toFixed(3)}%;width:${i.width.toFixed(3)}%" title=${a(t.name,r)}></span>`})}
            </div>
          </div>`)}
        ${n.live?O`<span class="tl-now" style="left:calc(120px + (100% - 120px) * ${o.toFixed(4)})"></span>`:k}
      </div>
      <div class="legend">
        <span><i class="py"></i>${N(`Python task`)}</span><span><i class="llm"></i>${N(`Agent task`)}</span>
      </div>
      <div class="legend">
        <span><i class="run"></i>${N(`running`)}</span><span><i class="bad"></i>${N(`failed`)}</span>
        <span><i class="idle"></i>${N(`not started`)}</span>
        ${n.hidden?O`<span>${n.hidden===1?N(`1 older attempt not shown`):N(M`${n.hidden} older attempts not shown`)}</span>`:k}
      </div>`}};W([H({attribute:!1})],Fs.prototype,`journal`,void 0),W([H({attribute:!1})],Fs.prototype,`procs`,void 0),W([H({type:Boolean})],Fs.prototype,`live`,void 0),W([H()],Fs.prototype,`run`,void 0),Fs=W([V(`ca-timeline`),P()],Fs);var Is=class extends A{constructor(...e){super(...e),this.procs=null,this.live=!1}static{this.styles=[B,c`
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
    `]}render(){let e=this.live?qr(this.procs):[],t=Math.max(this.procs?.max_workers||1,e.length),n=Array.from({length:t-e.length},(e,t)=>t);return O`<div class="wks" style="--n:${Math.min(t,6)}">
      ${X(e,e=>e.id,e=>O`<div class="wk ${e.cls}"
          @click=${e.key?()=>j(this,`ca-open-task`,{key:e.key}):k}>
          <div class="wk-top"><span class="wk-ic" title=${e.cls===`llm`?N(`Agent task`):N(`Python task`)}><span aria-hidden="true">${e.cls===`llm`?`✦`:`⚙`}</span><span class="sr">${e.cls===`llm`?N(`Agent task`):N(`Python task`)}</span></span><b>${e.kind}</b>
            <ca-elapsed class="wk-el" .since=${rr.at(e.id,e.ageS)}></ca-elapsed></div>
          <div class="meta">${e.detail}</div>
          <div class="wk-bar"><i></i></div>
        </div>`)}
      ${n.map(()=>O`<div class="wk idle"><div class="wk-top"><b>${N(`Idle`)}</b></div>
          <div class="meta">${N(`No task`)}</div></div>`)}
    </div>`}};W([H({attribute:!1})],Is.prototype,`procs`,void 0),W([H({type:Boolean})],Is.prototype,`live`,void 0),Is=W([V(`ca-workers`),P()],Is);var Ls=5,Rs=[`invalid`,`refused`,`failed`,`running`,`pending`,`valid`];function zs(e){if(e===void 0)return N(`Loading…`);if(typeof e!=`object`||!e)return JSON.stringify(e);let t=Object.keys(e);if(!t.length)return N(`Empty`);let n=`${t.slice(0,4).join(`, `)}${t.length>4?`, …`:``}`;return N(Array.isArray(e)?M`${t.length} items: ${n}`:M`${t.length} keys: ${n}`)}var Bs=class extends A{constructor(...e){super(...e),this.run=``,this.layer=``,this.unit=``,this.sel=``}static{this.styles=[B,c`
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
      .fl.muted .jstop { color: var(--text-2); font-weight: 500; }
      .fl.muted .jstop::before { content: '✓'; content: '✓' / ''; color: var(--status-done); margin-right: 0.35em; font-weight: 700; }
      .next { margin: 10px 2px 2px; font-size: 12px; color: var(--text-2); }
      .next code { font-family: var(--mono); }
      .more { font-size: 12px; margin: 6px 10px 0; }
    `]}go(e){j(this,`ca-navigate`,{tab:e})}open(e){j(this,`ca-open-task`,{key:e.key,...G(e)?{view:`output`}:{}})}render(){let e=this.state,t=Kr(e,this.summary),n=t?qr(e.procs).length:0,r=e.procs?.max_workers||1,i=this.info.panels;return O`<div class="g12">
      <section class="panel c5 enter">
        <h3>${N(`Run`)}</h3>
        <ca-run-driver .procs=${e.procs} .summary=${this.summary} .plan=${e.plan}></ca-run-driver>
      </section>
      <section class="panel c7 enter">
        <h3 title=${N(`Limit: max_concurrent`)}>${N(`Running tasks`)}
          ${t?O`<span class="r">${N(M`${n} of ${r} running at once`)}</span>`:k}</h3>
        ${t?O`<ca-workers .procs=${e.procs} .live=${t}></ca-workers>`:O`<div class="meta">${N(`No tasks running`)}</div>`}
      </section>
      <section class="panel c12 enter">
        <h3 title=${N(`Every task the run scheduled, by kind (plan.jsonl)`)}>${N(`Pipeline`)}
          <span class="r">${this.progressLine(t)}</span></h3>
        <ca-pipeline-graph .plan=${e.plan} .journal=${e.journal} .run=${this.run} .layer=${this.layer} .unit=${this.unit} .sel=${this.sel} ?live=${t}></ca-pipeline-graph>
      </section>
      <section class="panel c12 enter">
        <h3 title=${N(`Counted from every finished attempt (journal.jsonl)`)}>${N(`Totals`)}</h3>
        <ca-kpis .journal=${e.journal} .plan=${e.plan}></ca-kpis>
      </section>
      ${ci(e.journal)?O`<section class="panel c12 enter">
            <h3 title=${N(`Reported by the coding agents`)}>${N(`Tokens and cost by kind`)}</h3>
            <ca-spend-breakdown .journal=${e.journal}></ca-spend-breakdown>
          </section>`:k}
      ${hi(e.journal).length?O`<section class="panel c12 enter">
            <h3 title=${N(`Reported at each agent session start. Account-wide: every task that runs at once shares it.`)}>
              ${N(`Subscription usage`)}<span class="r">${N(`Per account, first → last reading`)}</span></h3>
            <ca-quota .journal=${e.journal}></ca-quota>
          </section>`:k}
      <section class="panel ${t?`c5`:`c12`} enter">
        <h3>${N(`Problems`)}
          <span class="r"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>j(this,`ca-navigate`,{tab:`journal`,stop:`bad`}))}>${N(`Failed attempts in history`)}</a></span></h3>
        ${this.problems(t)}
      </section>
      ${t?O`<section class="panel c7 enter">
            <h3>${N(`Process tree`)}
              <span class="r"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>this.go(`procs`))}>${N(`All processes`)}</a></span></h3>
            <ca-proc-tree .procs=${e.procs}></ca-proc-tree>
          </section>`:k}
      <section class="panel c12 enter">
        <h3 title=${N(`Checked files (OutputContract, InputContract)`)}>${N(`Outputs`)}
          <span class="r"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>this.go(`outputs`))}>${N(`All outputs`)}</a></span></h3>
        ${this.outputs()}
      </section>
      ${e.cursor?O`<section class="panel c12 enter">
            <h3 title=${N(`Stage and step per unit (CursorStore)`)}>${N(`Resume cursor`)}</h3>
            ${this.cursor()}
          </section>`:k}
      ${i.length?O`<section class="panel c12 enter">
            <h3 title=${N(`monitor.Panel`)}>${N(`Custom views`)}</h3>
            ${this.panelCards()}
          </section>`:k}
      <section class="panel c12 enter">
        <h3>${N(`Timeline`)}
          <span class="r">${this.triesLine()}</span></h3>
        <ca-timeline .journal=${e.journal} .procs=${e.procs} .live=${t} .run=${this.run}></ca-timeline>
      </section>
    </div>`}outputs(){let{contracts:e,tally:t}=this.state.outputs;if(!e.length)return O`<div class="meta">${N(`No output files`)}</div>`;let n=Rs.filter(e=>t[e]),r=e.flatMap(e=>(e.outputs??[]).map(t=>[e,t])).filter(([,e])=>e.status===`invalid`||e.status===`failed`),i=r.slice(0,Ls),a=t.refused;return O`<div class="ct-row">
        ${n.length?n.map(e=>O`<span class="ct-chip ${e}" title=${jo(e)}>${Ao(e)} <b>${t[e]}</b></span>`):O`<span class="meta">${N(`No checked files`)}</span>`}
      </div>
      ${i.map(([e,t])=>O`<div class="fl" @click=${()=>this.go(`outputs`)}>
          <span class="jstop j-${Lo(t.status)}" title=${t.status?jo(t.status):``}>${t.status?Ao(t.status):`—`}</span>
          <b class="jmono" title=${e.key}>${L({kind:e.kind,unit:e.unit===e.key?``:e.unit})}</b>
          <span class="meta">${Ko(t)}</span>
          <div class="meta">${J(t.errors?.[0]||t.path,this.run).slice(0,160)}</div>
        </div>`)}
      ${r.length>i.length?O`<div class="more"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>this.go(`outputs`))}>${r.length-i.length===1?N(`1 more output`):N(M`${r.length-i.length} more outputs`)}</a></div>`:k}
      ${a?O`<div class="meta more">${N(a===1?`1 output not written (task not started)`:M`${a} outputs not written (tasks not started)`)}</div>`:k}`}progressLine(e){let t=this.state.plan,n=Ki(t);if(e||n.left){let e=Wi(t);return I(N(M`${e.pct}%`),N(M`${e.done} of ${e.total} tasks done`))}return I(Si(`done`,n.done),n.failed?Si(`failed`,n.failed):``,n.notStarted?Si(`not_started`,n.notStarted):``)}triesLine(){let{tries:e,notStarted:t}=Gi(this.state.journal);return I(N(e===1?`1 attempt`:M`${e} attempts`),t?Si(`not_started`,t):``)}nav(e,t){e.preventDefault(),t()}cursor(){let e=this.state.cursor,t=Object.entries(e?.units??{});if(!e||!e.stage&&!t.length)return O`<div class="meta">${N(`No resume cursor`)}</div>`;let n=e.completed_stages??[];return O`<div class="chips" style="margin-bottom:10px">
        ${n.length||e.stage?O`${n.map(e=>O`<span class="chip done"><span aria-hidden="true">✓</span><span class="sr">${N(`done`)}</span> ${e}</span>`)}${e.stage?O`<span class="chip cur"><span class="sr">${N(`current`)}</span>${e.stage}</span>`:k}`:O`<span class="meta">${N(`No stage`)}</span>`}
      </div>
      ${t.length?O`<div class="cur-units">
            ${t.map(([e,t])=>O`<div class="cu">
                <span class="jmono">${e}</span>
                <span class="meta">${I(t.step||`—`,t.loop_pass?N(M`loop pass ${t.loop_pass}`):``)}</span>
                <span class="cu-bar" title=${t.completed.length===1?N(`1 step completed`):N(M`${t.completed.length} steps completed`)}><i style="width:${Math.min(100,12*(t.completed.length+1))}%"></i></span>
                ${t.inflight.length?O`<span class="pill p-running" title=${t.inflight.join(`
`)}>${N(`running`)}</span>`:k}
              </div>`)}
          </div>`:k}`}panelCards(){return O`<div class="pcards">
      ${X(this.info.panels,e=>e.name,e=>O`<button type="button" class="pcard" @click=${()=>this.go(`panel:${e.name}`)}>
          <span class="pc-ic" aria-hidden="true">${e.icon||`▤`}</span>
          <div>
            <b>${e.title||e.name}</b>
            ${e.description?O`<div class="meta">${e.description}</div>`:k}
            <div class="pc-peek">${zs(this.state.panels[e.name])}</div>
          </div>
          <span class="pc-go">${N(M`Show ${e.title||e.name}`)}</span>
        </button>`)}
    </div>`}name(e){return L(e)}problems(e){let t=Qr(this.state.journal,this.state.plan),{failed:n,notStarted:r}=$r(t),i=[...t.values()].filter(e=>e.outcome===`recovered`);if(!n.length&&!r.length&&!i.length)return O`<div class="blank" style="padding:22px"><span class="ic" aria-hidden="true">✓</span>${N(`No problems`)}</div>`;let a=e=>J(e.attempts[e.attempts.length-1]?.reason||`—`,this.run).slice(0,200),o=e=>e.length?O`<div class="stopped">
            <span>${e.length===1?N(`1 later task not started`):N(M`${e.length} later tasks not started`)}</span>
            ${e.map(e=>lo(this,this.name(e),e))}
          </div>`:k;return O`${X(n,e=>e.task.key,e=>{let t=e.task.attempts[e.task.attempts.length-1];return O`<div class="fl" @click=${()=>this.open(e.task)}>
            <span class="jstop j-error">${_i(`failed`)}</span>
            <b class="jmono" title=${e.task.key}>${this.name(e.task)}</b><span class="meta">${Sn(t?.ts,!0)}</span>
            <div class="meta">${q(t?.stop)}: ${a(e.task)}</div>
            ${o(e.stopped)}
          </div>`})}
      ${X(r,e=>e.key,e=>O`<div class="fl" @click=${()=>this.open(e)}>
          <span class="jstop j-invalid_input">${_i(`not_started`)}</span>
          <b class="jmono" title=${e.key}>${this.name(e)}</b><span></span>
          <div class="meta">${Li(e,t,this.run)?wn(Li(e,t,this.run)):a(e)}</div>
        </div>`)}
      ${X(i,e=>e.key,e=>{let t=e.tries.filter(e=>!e.ok).length,n=e.tries.length,r=this.name(e);return O`<div class="fl muted" @click=${()=>this.open(e)}>
            <span class="jstop">${_i(`recovered`)}</span>
            <b class="jmono" title=${e.key}>${r}</b><span></span>
            <div class="meta">${N(t===1?M`Done on attempt ${n} after 1 failed attempt`:M`Done on attempt ${n} after ${t} failed attempts`)}</div>
          </div>`})}
      ${this.nextStep(e,n.length+r.length)}`}nextStep(e,t){if(e||!t)return k;let n=ei(Qr(this.state.journal,this.state.plan)),r=n.total-n.done-n.recovered-n.skipped;return r?O`<div class="next" title="resume=True">${N(M`${r} of ${n.total} tasks not done`)}</div>`:k}};W([H({attribute:!1})],Bs.prototype,`state`,void 0),W([H({attribute:!1})],Bs.prototype,`summary`,void 0),W([H({attribute:!1})],Bs.prototype,`info`,void 0),W([H()],Bs.prototype,`run`,void 0),W([H()],Bs.prototype,`layer`,void 0),W([H()],Bs.prototype,`unit`,void 0),W([H()],Bs.prototype,`sel`,void 0),Bs=W([V(`ca-overview`),P()],Bs);function Vs(e,t,n){let r=n.toLowerCase();return e.filter(e=>(!t||e.kind===t)&&(!r||`${e.kind} ${e.unit} ${e.key} ${e.last_stop}`.toLowerCase().includes(r)))}var Hs={failed:0,not_started:1,running:2,waiting:3};function Us(e){return e.map((e,t)=>({t:e,i:t})).sort((e,t)=>(Hs[e.t.outcome]??9)-(Hs[t.t.outcome]??9)||t.t.last_ts.localeCompare(e.t.last_ts)||e.i-t.i).map(e=>e.t)}var Ws=[`key`,`unit`,`stop`,`kind`,`route`,`reason`];function Gs(e){let t=new Map;for(let n of e)K(n)&&t.set(n.key,(t.get(n.key)??0)+1);return new Set([...t].filter(([,e])=>e>1).map(([e])=>e))}var Ks=e=>(e.rounds??1)>1;function qs(e,t,n,r){let i=r.toLowerCase(),a=n===`retried`?Gs(e):null;return e.filter(e=>n===`bad`&&!Hr(e)||n===`fixup`&&!Ks(e)||a&&!a.has(e.key)||n&&![`bad`,`fixup`,`retried`].includes(n)&&e.stop!==n||t&&e.kind!==t?!1:!i||Ws.some(t=>String(e[t]??``).toLowerCase().includes(i)))}function Js(e){let t=new Map;for(let n of e)t.set(n.stop||`?`,(t.get(n.stop||`?`)??0)+1);return[...t.entries()].sort((e,t)=>t[1]-e[1])}function Ys(e){let t=new Map;return e.forEach((e,n)=>{let r=t.get(e.key)??{count:0,lastOk:-1,lastOkTry:0};K(e)&&r.count++,e.ok&&(r.lastOk=n,r.lastOkTry=(e.attempt??0)+1),t.set(e.key,r)}),t}var Xs=class extends A{constructor(...e){super(...e),this.journal=[],this.plan=null,this.kind=``,this.q=``,this.live=!1,this.run=``}static{this.styles=[B,c`
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
    `]}cause(e,t){return e.outcome===`not_started`?Li(e,t,this.run):e.outcome===`waiting`?yi(e.waits_for.map(e=>t.get(e)??{kind:e})):``}spendCells(e,t){return e?t?.reported?O`<span class="num" title=${I(N(M`Cache read ${z(t.cache_read)}`),N(M`Cache write ${z(t.cache_creation)}`))}>${z(t.input+t.output)}</span><span class="num">${En(t.cost)}</span>`:O`<span class="num jdim">—</span><span class="num jdim">—</span>`:O`<span class="num jdim">${N(`none`)}</span><span class="num jdim">${N(`none`)}</span>`}render(){let e=this.plan?ri(this.journal,this.plan):[],t=Us(Vs(e,this.kind,this.q));if(!t.length)return O`<div class="blank"><span class="ic" aria-hidden="true">≡</span>${e.length?N(`No tasks match the filter`):N(`No tasks`)}</div>`;let n=new Map(e.map(e=>[e.key,e])),r=new Map;for(let t of e)r.set(`${t.kind}|${t.unit}`,(r.get(`${t.kind}|${t.unit}`)??0)+1);let i=Math.max(1,...t.map(e=>e.wall_s)),a=new Map;for(let e of this.journal)si(a.get(e.key)??a.set(e.key,ai()).get(e.key),e);return O`<div class="trow hd">
        <span title=${N(`Kind · unit`)}>${N(`Task`)}</span><span class="num" title=${N(`Attempts that ran`)}>${N(`Attempts`)}</span>
        <span class="num" title=${N(`Sum over all attempts`)}>${N(`Time`)}</span>
        <span class="num" title=${N(`Input and output tokens, all attempts`)}>${N(`Tokens`)}</span>
        <span class="num" title=${N(`Reported by the coding agent`)}>${N(`Cost`)}</span>
        <span class="num">${N(`Last attempt ended`)}</span>
        <span class="st">${N(`Status`)}</span>
      </div>
      ${X(t,e=>e.key,e=>{let t=G(e),o=e.outcome===`running`,s=e.tries.length>0,c=this.cause(e,n),l=e.pass!==null&&(r.get(`${e.kind}|${e.unit}`)??0)>1?e.pass:null;return O`<div class="trow ${o?`running`:``} ${t?`py`:``}"
            @click=${()=>j(this,`ca-open-task`,t?{key:e.key,view:`output`}:{key:e.key})}>
            <span class="grow jmono" title=${e.key}>
              <span class="k-ic ${t?``:`llm`}" title=${N(t?`Python task`:`Agent task`)}><span aria-hidden="true">${t?`⚙`:`✦`}</span><span class="sr">${N(t?`Python task`:`Agent task`)}</span></span>${e.kind}
              ${e.unit?O`<span class="jdim">· ${e.unit}</span>`:k}${l===null?k:O`<span class="pass">${Ti(l)}</span>`}
            </span>
            <span class="num">${e.tries.length}</span>
            <span class="num wall">${s?O`${F(e.wall_s)}<span class="jdur"><i class=${t?``:`llm`}
                  style="width:${Math.max(4,Math.round(100*e.wall_s/i))}%"></i></span>`:O`<span class="jdim">${N(`none`)}</span><span class="jdur" style="visibility:hidden"></span>`}</span>
            ${this.spendCells(s,a.get(e.key))}
            <span class="num meta">${s?Sn(e.tries[e.tries.length-1]?.ts,!0):N(`none`)}</span>
            <span class="st"><span class="pill o-${e.outcome}" title=${e.last_stop}>${vi(e.outcome,this.live)}</span>${c?O`<span class="cause">${c}</span>`:k}</span>
          </div>`})}`}};W([H({attribute:!1})],Xs.prototype,`journal`,void 0),W([H({attribute:!1})],Xs.prototype,`plan`,void 0),W([H()],Xs.prototype,`kind`,void 0),W([H()],Xs.prototype,`q`,void 0),W([H({type:Boolean})],Xs.prototype,`live`,void 0),W([H()],Xs.prototype,`run`,void 0),Xs=W([V(`ca-task-table`),P()],Xs);var Zs=`grid-template-columns:64px minmax(130px,0.8fr) minmax(150px,0.7fr) minmax(150px,1fr) 92px 60px 76px minmax(200px,2.2fr)`,Qs=class extends A{constructor(...e){super(...e),this.rows=[],this.fresh=new Set,this.kind=``,this.stop=``,this.q=``,this.run=``,this.outcomes=new Map}static{this.styles=[B,c`
      :host { display: block; }
      .jtally { display: flex; flex-wrap: wrap; gap: 8px; padding: 2px 0 12px; }
      .jchip { border: 1px solid var(--line); border-radius: 999px; padding: 3px 11px; font-size: 11.5px; color: var(--text-muted);
        cursor: pointer; transition: all 0.15s; background: none; }
      .jchip b { color: var(--text); }
      .jchip:hover { border-color: var(--line2); color: var(--text); }
      .jchip.on { background: var(--accent-bg); border-color: var(--accent); color: var(--text); }
      /* a stop's chip: marked by its status (done quiet with a ✓, a failure red with a ✕, not started ◌) */
      .jchip.done::before { content: '✓'; content: '✓' / ''; color: var(--status-done); margin-right: 0.35em; font-weight: 700; }
      .jchip.failed { color: var(--status-failed); border-color: color-mix(in srgb, var(--status-failed) 40%, transparent); }
      .jchip.failed::before { content: '✕'; content: '✕' / ''; margin-right: 0.35em; font-weight: 700; }
      .jchip.attention { color: var(--status-attention); border-color: color-mix(in srgb, var(--status-attention) 40%, transparent); }
      .jchip.attention::before { content: '◌'; content: '◌' / ''; margin-right: 0.35em; font-weight: 700; }
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
    `]}render(){this.outcomes=Qr(this.rows,{nodes:[],groups:[]});let e=qs(this.rows,this.kind,this.stop,this.q).reverse(),t=Math.max(1,...e.map(e=>e.wall_s||0)),n=Ys(this.rows),r=new Map(this.rows.map((e,t)=>[e,t])),i=this.rows.filter(Ks).length,a=Gs(this.rows).size,o=(e,t,n,r,i=``)=>O`<button type="button" class="jchip j-${e} ${i} ${this.stop===e?`on`:``}" aria-pressed=${this.stop===e} title=${r}
        @click=${()=>j(this,`ca-filter`,{stop:this.stop===e?``:e})}>${t} <b>${n}</b></button>`;return O`<div class="jtally">
        ${Js(this.rows).map(([e,t])=>o(e,this.shortStop(e),t,e,Ui(e)))}
        ${i?o(`fixup`,N(`attempts with corrections`),i,N(`Attempts with at least one correction`)):k}
        ${a?o(`retried`,N(`tasks retried`),a,N(`Tasks with more than one attempt`)):k}
      </div>
      <div class="table">
      <div class="jrow hd" style=${Zs}>
        <span>${N(`Ended`)}</span><span>${N(`Task`)}</span>
        <span title=${N(`How the attempt ended (stop)`)}>${N(`Outcome`)}</span>
        <span>${N(`Agent, model, identity`)}</span>
        <span class="num" title=${N(`Input / output tokens, then cache read / cache write`)}>${N(`Tokens`)}</span>
        <span class="num" title=${N(`Reported by the coding agent`)}>${N(`Cost`)}</span>
        <span class="num">${N(`Time`)}</span><span>${N(`Reason`)}</span>
      </div>
      ${X(e,Wr,e=>{let i=n.get(e.key),a=!e.ok&&K(e)&&(i?.lastOk??-1)>(r.get(e)??0)?i?.lastOkTry??0:0;return this.row(e,t,(i?.count??1)>1,a)})}
      </div>
      ${e.length?k:O`<div class="meta" style="padding:8px">${N(`No finished attempts`)}</div>`}`}shortStop(e){return e===`invalid_input`?_i(`not_started`):q(e)}reason(e,t,n){let r=Pi(e.hops),i=this.run||e.run_id||``,a=this.outcomes.get(e.key),o=e.stop===`invalid_input`&&a?Li({attempts:[e],cause:null},this.outcomes,i):``,s=o?wn(o):(!e.ok||!t)&&e.reason?J(e.reason,i):``,c=n?N(M`The task was done on attempt ${n}`):``;return!r&&!s&&!c?O`<span class="jdim">—</span>`:O`${r?O`<span class="nw" title=${N(`Model switch`)}>${r}</span><br />`:k}${s?O`${s}<br />`:k}${c?O`<span class="later">${c}</span>`:k}`}identity(e){let t=[...new Set([...(e.hops??[]).map(e=>e.credential),e.credential].filter(Boolean))];if(!t.length)return k;let n=(e.quota??[])[0],r=n?N(M`Usage at session start (account-wide): ${oo(n)}`):``,i=n&&t.length===1&&(n.credential??``)===t[0],a=n?i?io(n):oo(n):``;return O`<span class="sub" title=${[r,...t.map(Mi)].filter(Boolean).join(`
`)||k}>${t.map(e=>ji(e)).join(` → `)}${n?O` <span class="q">${a}</span>`:k}</span>`}spend(e){let t=e.usage,n=e.hops??[],r=n.length>1?n.map(e=>I(e.model||e.route||`—`,ji(e.credential)||`—`,En(e.cost_usd),q(e.stop))).join(`
`):``;return O`<span class="num two">${t?O`<span>${z(t.input)} / ${z(t.output)}</span><span class="sub">${z(t.cache_read)} / ${z(t.cache_creation)}</span>`:O`<span class="jdim">—</span>`}</span>
      <span class="cost" title=${r||N(`Reported by the coding agent`)}>${En(e.cost_usd)}</span>`}row(e,t,n,r){let i=K(e),a=i&&Hr(e),o=G(e),s=Pi(e.hops),c=i?Ai((e.rounds??1)-1):``,l=N(o?`Python task`:`Agent task`);return O`<div class=${`jrow${a?` bad`:``}${i?``:` notrun`}${o?` py`:` agent`}${this.fresh.has(Wr(e))?` fresh`:``}`} style=${Zs}
      @click=${()=>j(this,`ca-open-task`,o?{key:e.key,view:`output`}:{key:e.key})}>
      <span class="jmono" title=${Sn(e.ts,!0)}>${Sn(e.ts)}</span>
      <span class="jmono" title=${e.key}><span title=${l}><span aria-hidden="true">${o?`⚙`:`✦`}</span><span class="sr">${l}</span></span>
        ${L(e)}</span>
      <span class="jstop two j-${e.stop||`?`}" title=${e.stop||``}><span class="nw">${this.shortStop(e.stop)}</span>${n&&i||c?O`<span class="sub">${I(n&&i?Ci(e.attempt):``,c)}</span>`:k}</span>
      <span class="jmono jdim two" title=${I(e.route,s)||k}>${i?O`<span>${[e.agent,e.model].filter(Boolean).join(` / `)||`—`}</span>${this.identity(e)}`:`—`}</span>
      ${this.spend(e)}
      <span class="num">${i?O`${F(e.wall_s)}<span class="jdur"><i class=${a?`bad`:o?``:`llm`}
            style="width:${Math.max(2,Math.round(100*(e.wall_s||0)/t))}%"></i></span>`:`—`}</span>
      <span class="jwhy" title=${e.reason||k}>${this.reason(e,i,r)}${Dn([e])?O` <span class="unread nw" title=${N(M`Event types from the coding agent that this contraagent version does not recognize: ${Dn([e])}`)}
            ><span aria-hidden="true">⚠</span> ${N(`Unrecognized events`)}</span
          >`:k}</span>
    </div>`}};W([H({attribute:!1})],Qs.prototype,`rows`,void 0),W([H({attribute:!1})],Qs.prototype,`fresh`,void 0),W([H()],Qs.prototype,`kind`,void 0),W([H()],Qs.prototype,`stop`,void 0),W([H()],Qs.prototype,`q`,void 0),W([H()],Qs.prototype,`run`,void 0),Qs=W([V(`ca-journal-table`),P()],Qs);var $s=[`invalid`,`refused`,`failed`,`running`,`pending`,`valid`];function ec(e){let t=e?.tally,n=t?$s.filter(e=>t[e]):[];return n.length?n.map(e=>O`<span class="ct-chip ${e}" title=${jo(e)}>${Ao(e)} <b>${t?.[e]}</b></span>`):O`<span class="meta">${N(`No checked files`)}</span>`}var tc=e=>e.split(`/`).slice(-2).join(`/`),nc=e=>L({kind:e.kind||e.key,unit:e.unit&&e.unit!==e.key?e.unit:``}),rc=e=>e?$s.indexOf(e):$s.length,ic=class extends A{constructor(...e){super(...e),this.outputs=null,this.run=``,this.journal=[],this.plan=null,this.outcomes=new Map,this.open=new Dt(`contracts:open`),this.producerOf=e=>{for(let t of this.outputs?.contracts??[]){let n=(t.outputs??[]).find(t=>t.path===e);if(n)return{name:nc(t),written:!!n.file.exists,outcome:this.outcomes.get(t.key)?.outcome}}}}static{this.styles=[B,Zo,c`
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
    `]}render(){let e=this.outputs?.contracts??[];if(this.outcomes=this.plan?Qr(this.journal,this.plan):new Map,!e.length)return O`<div class="blank"><span class="ic" aria-hidden="true">▣</span><b>${N(`No checked files`)}</b>
        <span>${N(`No task declares an OutputContract or an InputContract`)}</span></div>`;let t=e.flatMap(e=>(e.outputs??[]).map(t=>[e,t])).sort(([e,t],[n,r])=>rc(t.status)-rc(r.status)||e.key.localeCompare(n.key)),n=e.flatMap(e=>(e.inputs??[]).map(t=>[e,t]));return O`<div class="g12">
      <section class="panel c12">
        <h3 title=${N(`OutputContract`)}>${N(`Outputs`)}
          <span class="r">${N(`Files each task must write`)}</span></h3>
        <div class="ct-row">${ec(this.outputs)}</div>
        ${X(t,([e,t])=>`out|${e.key}|${t.path}`,([e,t])=>this.outRow(e,t))}
      </section>
      ${n.length?O`<section class="panel c12">
            <h3 title=${N(`InputContract`)}>${N(`Inputs`)}
              <span class="r">${N(`Files each task reads, checked when the task starts`)}</span></h3>
            ${X(n,([e,t])=>`in|${e.key}|${t.path}`,([e,t])=>this.inRow(e,t))}
          </section>`:k}
    </div>`}details(e,t,n){return O`<details class="ct" ?open=${this.open.has(e)}
      @toggle=${t=>this.open.set(e,t.target.open)}>
      <summary class="ct-sum">${t}</summary>
      <div class="ct-body">${n}</div>
    </details>`}link(e,t,n){return O`<a class="lnk" href="#" @click=${n=>{n.preventDefault(),j(this,`ca-open-task`,{key:e,view:t})}}>${n}</a>`}who(e){let t=G(e),n=N(t?`Python task`:`Agent task`);return O`<span class="k-ic ${t?``:`llm`}" title=${n}><span aria-hidden="true">${t?`⚙`:`✦`}</span><span class="sr">${n}</span></span>
      <b class="jmono" title=${e.key}>${nc(e)}</b>`}reasonOf(e){for(let t=this.journal.length-1;t>=0;t--){let n=this.journal[t];if(n?.key===e)return J(n.reason,this.run)}return``}outRow(e,t){if(t.status===`refused`)return O`<div class="one">
        <span class="ct-chip refused" title=${jo(`refused`)}>${Ao(`refused`)}</span>${this.who(e)}
        <span class="why">${Jo(t,this.run,this.producerOf)}</span>
      </div>`;let n=t.file,r=t.status,i=t.rounds??0,a=t.errors??[],o=nc(e);return this.details(`out|${e.key}|${t.path}`,O`<span class="ct-chip ${r??``}" title=${r?jo(r):``}>${r?Ao(r):`—`}</span>
        ${i>1?O`<span class="meta" title=${Mo()}>${No(i,r===`valid`)}</span>`:k}
        ${this.who(e)}
        <span class="jmono jdim ct-path" title=${t.path}>${tc(t.path)}</span>
        ${r===`failed`&&this.reasonOf(e.key)?O`<span class="why">${this.reasonOf(e.key)}</span>`:k}
        <span class="meta ct-f">${n.exists?`${n.size??0} B`:r?k:N(`No file`)}</span>`,O`${Yo(t,`output`)}
        ${Uo(t)}
        ${a.length?O`<h4>${N(`Errors`)}</h4><pre class="ct-err">${a.map(e=>J(e,this.run)).join(`
`)}</pre>`:k}
        <div class="ct-links">
          ${this.link(e.key,`output`,N(M`${o}: input and output`))}
          ${G(e)?k:O`<br />${this.link(e.key,`transcript`,N(M`${o}: transcript`))}`}
        </div>`)}inRow(e,t){let n=t.file,r=!!n.exists;return this.details(`in|${e.key}|${t.path}`,O`${Fo(t)}
        ${this.who(e)}
        <span class="jmono jdim ct-path" title=${t.path}>${tc(t.path)}</span>
        <span class="meta ct-f">${r?`${n.size??0} B`:N(`No file`)}</span>`,O`${Yo(t,`input`)}
        ${Uo(t)}
        <div class="ct-links">${this.link(e.key,`input`,N(M`${nc(e)}: input`))}</div>`)}};W([H({attribute:!1})],ic.prototype,`outputs`,void 0),W([H()],ic.prototype,`run`,void 0),W([H({attribute:!1})],ic.prototype,`journal`,void 0),W([H({attribute:!1})],ic.prototype,`plan`,void 0),ic=W([V(`ca-contracts`),P()],ic);var ac=3e3,oc=class extends A{constructor(...e){super(...e),this.run=``,this.live=!1,this.journal=[],this.plan=null,this.selected=null,this.defs=[],this.defsRun=``,this.timer=null}static{this.styles=[B,c`
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
    `]}disconnectedCallback(){super.disconnectedCallback(),this.clearTimer(),this.defsRun=``}connectedCallback(){super.connectedCallback(),this.run&&this.defsRun!==this.run&&this.load()}willUpdate(e){(e.has(`run`)||e.has(`client`))&&this.run&&this.client&&this.defsRun!==this.run&&(this.defs=[],this.load())}updated(){let e=new Set(this.tasks().filter(e=>!G(e)&&(e.tries.length||e.outcome===`running`)).map(e=>e.kind)).size;this.live&&this.defsRun===this.run&&this.defs.length<e&&!this.timer&&(this.timer=setTimeout(()=>{this.timer=null,this.load()},ac))}tasks(){return[...Qr(this.journal,this.plan??{nodes:[],groups:[]}).values()]}clearTimer(){this.timer&&clearTimeout(this.timer),this.timer=null}async load(){if(!this.client||!this.run)return;let e=this.run;this.defsRun=e;let t=[];try{t=await this.client.definitions(e)}catch{t=[]}e===this.run&&(this.defs=t)}render(){let e=this.defs,t=this.tasks(),n=[...new Set(t.filter(e=>G(e)).map(e=>e.kind))].filter(t=>!e.some(e=>e.kind===t));if(!e.length&&!n.length)return O`<div class="blank"><span class="ic" aria-hidden="true">⌘</span><b>${this.live?N(`No definitions yet`):N(`No definitions`)}</b></div>`;let r=this.selected!==null&&n.includes(this.selected)?this.selected:null,i=r?void 0:e.find(e=>e.kind===this.selected)??e.find(e=>e.plugin)??e[0],a=r??i?.kind??n[0]??``,o=e=>{let n=t.filter(t=>t.kind===e),r=n.length,i=n.reduce((e,t)=>e+t.tries.length,0);return I(N(r===1?`1 task`:M`${r} tasks`),N(i===1?`1 attempt`:M`${i} attempts`))};return O`<div class="defs">
      <div class="deflist">
        ${X(e,e=>e.kind,e=>O`<div class="defitem ${e.kind===a?`sel`:``}" @click=${()=>j(this,`ca-navigate`,{def:e.kind})}>
            <b class="jmono">${e.kind}</b>
            <span class="meta words">${$o(I(e.executor===`python`?`Python`:e.role?N(M`Role ${e.role}`):N(`No role`),o(e.kind)))}</span>
          </div>`)}
        ${X(n,e=>e,e=>O`<div class="defitem ${e===a?`sel`:``}" @click=${()=>j(this,`ca-navigate`,{def:e})}>
            <b class="jmono">${e}</b>
            <span class="meta words">${$o(I(`Python`,o(e)))}</span>
          </div>`)}
      </div>
      <section class="panel">
        ${i?O`<h3 title=${N(`As recorded when its first task started (definitions/<kind>.json)`)}>
                ${i.kind}<span class="r">${i.executor===`python`?N(`Python task`):i.plugin?N(M`Plugin ${i.name||``}`):N(`Defined in Python code`)}</span>
              </h3>
              <ca-definition .definition=${i} memory="definition:${i.kind}"></ca-definition>`:O`<h3>${a}<span class="r">${N(`Python task`)}</span></h3>
              <ca-definition .definition=${null}></ca-definition>`}
      </section>
    </div>`}};W([H({attribute:!1})],oc.prototype,`client`,void 0),W([H()],oc.prototype,`run`,void 0),W([H({type:Boolean})],oc.prototype,`live`,void 0),W([H({attribute:!1})],oc.prototype,`journal`,void 0),W([H({attribute:!1})],oc.prototype,`plan`,void 0),W([H({attribute:!1})],oc.prototype,`selected`,void 0),W([U()],oc.prototype,`defs`,void 0),oc=W([V(`ca-definitions`),P()],oc);var sc=class extends A{constructor(...e){super(...e),this.procs=null}static{this.styles=[B,c`
      :host { display: block; }
      .cmd { word-break: break-all; }
    `]}render(){let e=this.procs;if(!e?.alive)return O`<div class="blank"><span class="ic" aria-hidden="true">⚙</span><b>${I(N(`No processes`),N(`run not running`))}</b></div>`;let t=e.python_tasks;return O`<div class="g12">
      <section class="panel c12">
        <h3 title=${N(`One per task (Backend.run)`)}>${N(`Agent sessions running`)} <span class="r">${e.launches.length}</span></h3>
        ${e.launches.length?X(e.launches,e=>e.key,e=>O`<div class="fl" @click=${()=>j(this,`ca-open-task`,{key:e.key})}>
                <b class="jmono">${L(e)}</b>
                <span class="meta">${I(N(M`PID ${e.pid}`),N(M`Model ${e.model||`—`}`),e.role?N(M`Role ${e.role}`):``)} |
                  <ca-elapsed .since=${rr.at(`c:${e.key}`,e.age_s)}></ca-elapsed></span>
                <div class="meta mono cmd">${(e.full_cmd||N(`In the pipeline process`)).slice(0,400)}</div>
              </div>`):O`<div class="meta">${N(`No agent sessions`)}</div>`}
      </section>
      ${t.length?O`<section class="panel c12">
            <h3 title=${N(`Functions in the pipeline process`)}>${N(`Python tasks running`)} <span class="r">${t.length}</span></h3>
            ${X(t,e=>e.key,e=>O`<div class="fl">
                <b class="jmono">${L(e)}</b>
                <span class="meta">${N(M`PID ${e.pid}`)} | <ca-elapsed .since=${rr.at(`p:${e.key}`,e.age_s)}></ca-elapsed></span>
              </div>`)}
          </section>`:k}
      <section class="panel c12"><h3>${N(`Process tree`)}</h3><ca-proc-tree .procs=${e}></ca-proc-tree></section>
    </div>`}};W([H({attribute:!1})],sc.prototype,`procs`,void 0),sc=W([V(`ca-procs-view`),P()],sc);var cc=class extends A{constructor(...e){super(...e),this.name=``}static{this.styles=[B,c`
      :host { display: block; }
      .tab-ic { opacity: 1; margin-right: 6px; font-size: 12px; }
      .desc { margin: -4px 0 12px; }
    `]}render(){if(this.data===void 0)return this.panel?O`<div class="blank"><span class="ic" aria-hidden="true">…</span>${N(`Loading…`)}</div>`:O`<div class="blank"><span class="ic" aria-hidden="true">▤</span>${N(M`No custom view named ${this.name}`)}</div>`;let e=this.panel;return O`<section class="panel">
      <h3><span class="tab-ic" aria-hidden="true">${e?.icon||`▤`}</span>${e?.title||this.name}
        <span class="r">${N(`Custom view`)}</span></h3>
      ${e?.description?O`<div class="meta desc">${e.description}</div>`:k}
      <ca-json-tree .value=${this.data}></ca-json-tree>
    </section>`}};W([H()],cc.prototype,`name`,void 0),W([H({attribute:!1})],cc.prototype,`panel`,void 0),W([H({attribute:!1})],cc.prototype,`data`,void 0),cc=W([V(`ca-panel-view`),P()],cc);var lc=e=>!e.file.exists||e.status!=null&&e.status!==`valid`;function uc(e){let t=new Set(e.inputs.map(e=>e.path)),n=e.inputs.map(t=>{for(let n of e.upstream){let e=n.outputs.find(e=>e.path===t.path);if(e)return{spec:t,from:n,out:e}}return{spec:t,from:null,out:null}}),r=e.upstream.map(e=>({task:e,read:e.outputs.filter(e=>t.has(e.path)).length,rest:e.outputs.filter(e=>!t.has(e.path))})),i=e=>Number(e.task.outputs.some(lc));return{files:n,earlier:[...r].sort((e,t)=>i(t)-i(e))}}function dc(e,t,n=Ci(e.tryNo-1)){return t>1?e.fixupNo?I(n,N(M`correction ${e.fixupNo}`)):e.hopNo?I(n,N(`model switch`)):n:e.fixupNo?N(M`Correction ${e.fixupNo}`):e.hopNo?N(`Model switch`):Ci(0)}function fc(e,t=!1){return e.fixupNo?N(`same agent session, after failed checks`):e.hopNo?N(`new agent session on the next model`):e.tryNo>1&&t?N(`new agent session in the resumed run`):e.tryNo>1?N(M`new agent session after attempt ${e.tryNo-1} failed`):N(`first agent session`)}function pc(e){let t=e.model||N(`model`);return e.switchedTo?N(M`${t}: ${q(e.switchedStop)}; switched to ${e.switchedTo}`):N(M`${t}: ${q(e.switchedStop)}; switched to the next model`)}function mc(e,t){switch(e.result){case`ok`:return[`✓`,N(`passed`),N(`Output passed checks`)];case`rejected`:return[`✕`,N(`failed checks`),N(`Output failed checks`)];case`switched`:return[`✕`,q(e.switchedStop),pc(e)];case`failed`:return[`✕`,N(`failed`),J(e.row?.reason,t)||q(e.row?.stop)];default:return[``,``,``]}}var hc={claude:`Claude Code`,omp:`omp`,codex:`Codex`,opencode:`opencode`,gemini:`Gemini CLI`};function gc(e){let t=String(e||``).split(`/`).pop()??``;return hc[t]??t}var _c=(e,t)=>{let n=e.indexOf(t);return n>=0?e[n+1]??``:``};function vc(e){let t=e.argv,n=/TELEMETRY [^\n]*role=([\w:-]+)/.exec(e.prompt||``)?.[1];return{agent:gc(t[0]),model:_c(t,`--model`)||_c(t,`-m`),role:n&&n!==`-`?n:``}}var yc=()=>({rounds:[],tools:new Map,next:0}),bc=/session init:.*?model=([\w.\-:]+)/;function xc(e){return`i${e.next++}`}function Sc(e,t){let n={id:`r${e.rounds.length}`,launch:t,who:t?vc(t):null,items:[]};return e.rounds.push(n),n}function Cc(e){return e.rounds[e.rounds.length-1]??Sc(e,null)}function wc(e,t){t?e.name=t:e.name||=`tool`,e.icon=(e.name.split(/[_:]/).pop()??``).toLowerCase()}function Tc(e,t,n){let r=n?e.tools.get(n):void 0;return r||(r={kind:`tool`,id:n?`call:${n}`:xc(e),call:n,name:``,icon:``,preview:``,intent:``,cmd:``,webQuery:``,webFetch:``,out:null,status:`run`},n&&e.tools.set(n,r),t.items.push(r)),r}function Ec(e,t){let n=0;for(let r of t){let t=_r(r);if(!t)continue;if(t.type===`launch`){Sc(e,t),n++;continue}let i=Cc(e);switch(t.type){case`message_start`:case`message_end`:if(t.role!==`user`||!t.text)continue;i.items.push({kind:`prompt`,id:xc(e),text:t.text});break;case`turn_end`:if(!t.thinking)continue;i.items.push({kind:`summary`,id:xc(e),text:t.thinking});break;case`acall`:case`tool_execution_start`:case`tool_execution_update`:{let n=Tc(e,i,t.call);n.out===null?(wc(n,t.tool),n.preview=Tn(t.cmd),n.intent=t.intent||``,n.cmd=t.cmd||n.cmd,t.web_query&&(n.webQuery=t.web_query),t.web_fetch&&(n.webFetch=t.web_fetch)):!n.preview&&t.cmd&&(n.preview=Tn(t.cmd));break}case`aresult`:case`tool_execution_end`:{let n=Tc(e,i,t.call);if(n.out!==null&&!t.out)break;wc(n,t.tool),n.status=t.err?`err`:`ok`,!n.preview&&n.cmd&&(n.preview=Tn(n.cmd)),n.out=t.out||`(no output)`;break}case`message_update`:{if(!t.delta)continue;let n=i.items[i.items.length-1];n?.kind===`assistant`?n.raw+=t.delta:i.items.push({kind:`assistant`,id:xc(e),raw:t.delta});break}case`auto_retry_start`:i.items.push({kind:`retry`,id:xc(e),err:t.err??``});break;case`notice`:{let n=bc.exec(t.text||``)?.[1];n&&(i.who??={agent:``,model:``,role:``},i.who.model||(i.who.model=n)),i.items.push({kind:`notice`,id:xc(e),text:(t.text||``).replace(/\s+/g,` `).trim()});break}}n++}return n}var Dc=`The output file(s) you wrote do not pass their checks.`;function Oc(e){let t=[],n=!1;for(let r of(e||``).split(`
`))/^Errors:\s*$/.test(r)?n=!0:n&&r.startsWith(`- `)?t.push(r.slice(2)):n&&r.trim()&&!r.startsWith(`- `)&&(n=!1);return t}var kc=e=>!!e&&(e.prompt||``).startsWith(Dc);function Ac(e,t){let n=new Map(t.filter(e=>e.stop!==`invalid_input`&&e.stop!==`skipped`).map((e,t)=>[t+1,e])),r=[],i=0,a=0,o=0;return e.forEach((e,t)=>{let s=n.get(i)?.hops?.length??1;t>0&&kc(e)?a++:t>0&&o+1<s?(o++,a=0):(i++,o=0,a=0);let c=n.get(i)?.hops?.[o],l=c?.model||c?.route||``,u=a?`fixup`:o?`switch`:`try`;r.push({kind:u,tryNo:i,fixupNo:a,hopNo:o,model:l,result:null,rejectedWith:[],switchedStop:``,switchedTo:``,row:null})}),r.forEach((t,i)=>{let a=r[i+1];if(a&&a.tryNo===t.tryNo&&a.hopNo!==t.hopNo){t.result=`switched`,t.switchedStop=n.get(t.tryNo)?.hops?.[t.hopNo]?.stop??``,t.switchedTo=a.model;return}if(a&&a.tryNo===t.tryNo){t.result=`rejected`,t.rejectedWith=Oc(e[i+1]?.prompt);return}let o=n.get(t.tryNo)??null;t.row=o,t.result=o?o.ok?`ok`:`failed`:null}),r}function jc(e){let t=/\[([\w.-]+)\]\s*(.*)$/.exec(e);return t?`${t[1]}: ${t[2]}`:e}var Mc=20,Nc=/\{\s*"title"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"url"\s*:\s*"(https?:\/\/[^"\s]+)"/g,Pc=/^\s*\[\d+\]\s+(.+)\n\s*(https?:\/\/\S+)/gm,Fc=/https?:\/\/[^\s"'<>)\]]+/g;function Ic(e){let t=e??``,n=[],r=new Set,i=(e,t)=>{r.has(t)||n.length>=Mc||(r.add(t),n.push({title:e.trim()||t,url:t}))};for(let e of t.matchAll(Nc)){let t=e[1]??``;try{t=JSON.parse(`"${t}"`)}catch{}i(t,e[2]??``)}if(!n.length)for(let e of t.matchAll(Pc))i(e[1]??``,e[2]??``);if(!n.length)for(let e of t.matchAll(Fc))i(``,e[0].replace(/[.,;:!?]+$/,``));return n}function Lc(e){return e?O`${e.agent?O`<span class="who agent" title=${N(`The CLI that ran the task (claude, omp)`)}
        ><span class="who-l">${N(`coding agent`)}</span>${e.agent}</span
      >`:k}${e.model?O`<span class="who model" title=${N(`The language model the coding agent used`)}
        ><span class="who-l">${N(`model`)}</span>${e.model}</span
      >`:k}${e.role?O`<span class="who role" title=${N(`The agent definition the coding agent ran as (agents/<role>.md)`)}
        ><span class="who-l">${N(`role`)}</span>${e.role}</span
      >`:k}`:O``}var Rc=c`
  .who { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; font-weight: 600; padding: 2px 9px;
    border-radius: 7px; border: 1px solid var(--line2); white-space: nowrap; }
  /* facts, not statuses: neutral chips, the label muted and the value in the text colour */
  .who-l { font-size: 10px; font-weight: 400; color: var(--text-muted); font-family: var(--sans); }
  .who.agent, .who.model { color: var(--text); background: var(--raise); }
  .who.model { font-family: var(--mono); }
  .who.role { color: var(--text-2); font-family: var(--mono); font-weight: 500; }
`,zc=60,Bc=1200,Vc=4e3,Hc=3e3,Uc=4e3;function Wc(e){try{return new URL(e).host}catch{return``}}var Q=class extends A{constructor(...e){super(...e),this.events=null,this.run=``,this.stream=null,this.baseUrl=``,this.client=null,this.live=!1,this.round=null,this.rows=[],this.mode=`full`,this.version=0,this.behind=0,this.bulk=!0,this.unseen=0,this.pinned=null,this.revealed=``,this.revealPending=!1,this.model=yc(),this.close=null,this.loaded=``,this.token=0,this.first=!0,this.stick=!0,this.restored=!1,this.lastTop=0,this.lastShown=-1,this.lastSent=``,this.openCards=new Ot(`transcript::open`),this.folds=new Set,this.openPrompts=new Set,this.mdCache=new WeakMap}static{this.styles=[B,Kn,Rc,c`
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
      .verdict.rejected { border-color: color-mix(in srgb, var(--status-attention) 40%, transparent); background: var(--status-attention-bg); color: var(--text); }
      .verdict.failed { border-color: color-mix(in srgb, var(--status-failed) 45%, transparent); background: var(--status-failed-bg); color: var(--text); }
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
    `]}get source(){return this.events?`static`:this.run&&this.stream?`${this.run}\n${this.stream}`:``}get memoryId(){return`transcript:${this.run}/${this.stream??``}`}disconnectedCallback(){super.disconnectedCallback(),this.close?.(),this.close=null,this.loaded=``}connectedCallback(){super.connectedCallback(),this.hasUpdated&&this.requestUpdate()}willUpdate(e){let t=this.source;(e.has(`events`)||t!==this.loaded)&&this.load(t)}load(e){if(this.close?.(),this.close=null,this.loaded=e,this.token++,this.model=yc(),this.first=!0,this.behind=0,this.bulk=!0,this.unseen=0,this.pinned=null,this.stick=!0,this.restored=!1,this.lastShown=-1,this.folds.clear(),this.openPrompts.clear(),this.openCards=new Ot(`${this.memoryId}:open`),this.events){Ec(this.model,this.events),this.version++,this.afterFirstPage(this.token);return}if(!e||!this.stream)return;let t=this.token;this.close=Rr(this.run,this.stream,{message:e=>this.onPage(e,t)},{baseUrl:this.baseUrl})}onPage(e,t){if(t!==this.token)return;this.first&&e.behind&&(this.behind=e.behind);let n=this.model.rounds.length,r=Ec(this.model,e.events);if(n&&this.model.rounds.length>n&&this.round===null&&this.pinned===null&&!this.stick&&!this.bulk&&(this.pinned=n),this.version++,this.first){this.first=!1,this.afterFirstPage(t);return}this.updateComplete.then(()=>{t===this.token&&(this.stick&&this.onLiveRound()?this.toBottom():this.unseen+=r)})}async afterFirstPage(e){if(await this.updateComplete,e!==this.token)return;let t=this.stream?wt(`${this.memoryId}:scroll`):void 0,n=this.scroller;if(!t||t.stick||!n)this.stick=!0,this.toBottom();else{this.stick=!1;let r=performance.now()+Uc;await new Promise(i=>{let a=()=>{let o=n.scrollHeight-n.clientHeight;n.scrollTop=Math.min(t.top,o),o>=t.top||performance.now()>r||e!==this.token?i():requestAnimationFrame(a)};a()}),this.lastTop=n.scrollTop}this.restored=!0,requestAnimationFrame(()=>{e===this.token&&(this.bulk=!1)})}shownIndex(){let e=this.model.rounds.length;if(!e)return-1;let t=this.round===null?this.pinned??e-1:this.round-1;return Math.max(0,Math.min(e-1,t))}onLiveRound(){let e=this.model.rounds.length;return e<2||this.shownIndex()===e-1}toBottom(e=!1){let t=this.scroller;t&&(e?t.scrollTo({top:t.scrollHeight,behavior:`smooth`}):t.scrollTop=t.scrollHeight)}onScroll(){let e=this.scroller;e&&e.clientHeight&&(this.stick=e.scrollHeight-e.scrollTop-e.clientHeight<zc,this.lastTop=e.scrollTop,this.stick&&this.onLiveRound()&&(this.unseen=0),this.restored&&this.stream&&Tt(`${this.memoryId}:scroll`,{stick:this.stick,top:Math.round(e.scrollTop)}))}updated(e){let t=this.shownIndex();if(t!==this.lastShown){let e=this.lastShown;this.lastShown=t,e!==-1&&this.restored&&this.toBottom()}let n=e.get(`mode`);n&&n!==`full`&&this.mode===`full`&&this.scroller&&(this.stick?this.toBottom():this.scroller.scrollTop=this.lastTop);let r=`${this.version}|${t}|${this.model.rounds.length}|${this.rows.length}`;if(r!==this.lastSent){this.lastSent=r;let e={launches:this.model.rounds.map(e=>e.launch),shown:t,rounds:this.infos()};this.dispatchEvent(new CustomEvent(`rounds-changed`,{detail:e}))}if(this.revealPending){let e=this.renderRoot.querySelector(`[data-card="${CSS.escape(this.revealed)}"]`);e&&this.mode===`full`&&(this.revealPending=!1,this.stick=!1,e.scrollIntoView({block:`center`}))}}infos(){return Ac(this.model.rounds.map(e=>e.launch),this.rows)}pickRound(e){this.pinned=null;let t=this.model.rounds.length-1;j(this,`ca-navigate`,{round:e===t?null:e+1})}jumpToLive(){let e=this.model.rounds.length;e>1&&this.shownIndex()!==e-1&&(this.pinned=null,this.round!==null&&j(this,`ca-navigate`,{round:null})),this.stick=!0,this.unseen=0,this.updateComplete.then(()=>this.toBottom(!0))}async loadEarlier(){let{run:e,stream:t}=this;if(!t)return;let n=this.token,r=Math.max(0,this.behind-Hc);this.behind=0;let i=await(this.client??Nr({baseUrl:this.baseUrl})).stream(e,t,r);n===this.token&&(this.model=yc(),this.lastShown=-1,Ec(this.model,i.events),this.version++)}render(){let e=this.model.rounds,t=this.shownIndex(),n=e[t],r=this.onLiveRound();return O`${this.renderRounds(e,t)}
      <div class="scroller ${this.bulk?`bulk`:``}" @scroll=${()=>this.onScroll()}>
        ${this.behind?O`<div class="meta"><button type="button" class="back" @click=${()=>void this.loadEarlier()}>
              ${this.behind===1?N(`Show 1 earlier line`):N(M`Show ${this.behind} earlier lines`)}</button></div>`:k}
        ${n?this.renderRound(n,t===e.length-1,this.infos()[t]):k}
        ${!n&&this.live?this.typing():k}
      </div>
      ${this.unseen?O`<button type="button" class="newpill" @click=${()=>this.jumpToLive()}>
            ${this.unseen===1?N(r?`Show 1 new event`:`Show 1 new event in the running agent session`):N(r?M`Show ${this.unseen} new events`:M`Show ${this.unseen} new events in the running agent session`)}</button>`:k}`}renderRounds(e,t){if(e.length<2)return k;let n=e.length-1,r=this.infos(),i=r[r.length-1]?.tryNo??1,a=wi(this.rows.filter(K));return O`<div class="rounds" role="group" aria-label=${N(`Agent sessions`)}>
      <span class="rounds-lbl"
        title=${[N(`Attempt: a new agent session`),N(`Correction: the same agent session after failed checks`),N(`Model switch: a new agent session on the next model`)].join(`
`)}
        >${N(`Agent sessions`)}</span>
      ${e.map((e,o)=>{let s=r[o],[c,l,u]=s?mc(s,this.run):[``,``,``];return O`<button type="button" class="stab ${o===t?`sel`:``}" title=${u||k} aria-pressed=${o===t}
          @click=${()=>this.pickRound(o)}>
          ${c?O`<span class="mk ${c===`✓`?`ok`:`bad`}" aria-hidden="true">${c}</span><span class="sr">${l}</span>`:k}${s?dc(s,i,a[s.tryNo-1]):String(o+1)}
          ${e.who?.model?O` <span class="stab-m">${e.who.model.replace(/^claude-/,``)}</span>`:k}
          ${o===n&&this.live&&this.close?O`<span class="dot running"></span>`:k}
        </button>`})}
    </div>`}renderRound(e,t,n){return O`<div class="inv-body">
      ${e.launch?this.renderHead(e,e.launch):k}
      ${X(e.items,e=>e.id,e=>this.renderItem(e))}
      ${t&&this.live?this.typing():k}
      ${n?this.renderVerdict(n):k}
    </div>`}renderVerdict(e){if(e.result===`rejected`)return O`<div class="verdict rejected">
        <b>${N(`Output failed checks`)}</b>
        ${e.rejectedWith.length?O`<ul>${e.rejectedWith.map(e=>O`<li>${J(e,this.run)}</li>`)}</ul>`:O`<span class="meta">${N(`The errors are in the correction prompt`)}</span>`}
      </div>`;if(e.result===`switched`)return O`<div class="verdict failed">
        <b>${pc(e)}</b>
      </div>`;if(e.result===`failed`&&e.row){let t=J(e.row.reason,this.run)||q(e.row.stop);return O`<div class="verdict failed"><b>${N(M`Attempt ${e.tryNo} failed: ${t}`)}</b></div>`}return k}renderHead(e,t){let n=t.prompt||``,r=t.prompt_truncated||0,i=this.openPrompts.has(e.id);return O`<div class="inv-head">
      <div class="inv-who">${Lc(e.who)}</div>
      <details class="inv-cmdbox"><summary>${N(`Command line`)}</summary><pre class="inv-cmd"><code>${t.argv.join(` `)}</code></pre></details>
      <details class="inv-prompt" ?open=${i}
        @toggle=${t=>{let n=t.target.open;n!==this.openPrompts.has(e.id)&&(n?this.openPrompts.add(e.id):this.openPrompts.delete(e.id),this.requestUpdate())}}>
        <summary>${N(r?M`Prompt (${n.length} characters; ${r} characters not saved)`:M`Prompt (${n.length} characters)`)}</summary>
        ${i?O`<div class="inv-ptext"><ca-markdown .text=${n+(r?`\n\n${N(M`(${r} characters not saved)`)}`:``)}></ca-markdown></div>`:k}
      </details>
    </div>`}mdOf(e,t){let n=this.mdCache.get(e);if(n?.raw===t)return n.html;let r=Bn(t);return this.mdCache.set(e,{raw:t,html:r}),r}bubble(e,t,n,r,i){return O`<div class="msg" title=${i??k}>
      <div class="av ${t}">${e}</div>
      <div class="bd"><div class="hd">${n}</div>${r}</div>
    </div>`}renderItem(e){switch(e.kind){case`prompt`:return this.bubble(`▸`,`av-l`,N(`Prompt`),O`<div class="tx meta">${N(M`${e.text.length} characters`)}</div>`,e.text.slice(0,600));case`assistant`:return this.bubble(`A`,`av-a`,N(`Assistant`),O`<div class="tx">${dr(this.mdOf(e,e.raw))}</div>`);case`summary`:return this.bubble(`✦`,`av-t`,N(`Reasoning`),O`<div class="tx">${dr(this.mdOf(e,e.text))}</div>`);case`retry`:return O`<div class="msg"><div class="av av-t" aria-hidden="true">↻</div><div class="bd"><div class="hd">${N(`API request sent again`)}</div>${e.err?O`<div class="tx meta">${e.err}</div>`:k}</div></div>`;case`notice`:return O`<div class="sysline"><span aria-hidden="true">⚙</span><span class="tx">${e.text}</span></div>`;case`tool`:return this.toolCard(e)}}toolCard(e){let t=this.openCards.has(e.id),n=e.webQuery?Ic(e.out):[],r=e.status===`ok`?O`<span class="st-ok"><span aria-hidden="true">✓</span> ${N(`done`)}</span>`:e.status===`err`?O`<span class="st-err"><span aria-hidden="true">✕</span> ${N(`failed`)}</span>`:this.live?O`<span class="st-run"><i class="pdot"></i>${N(`running`)}</span>`:O`<span class="st-int" title=${N(`The run ended before the tool call returned`)}><span aria-hidden="true">◌</span> ${N(`interrupted`)}</span>`,i=e.webQuery?`web-search`:e.webFetch?`web-fetch`:e.icon;return O`<div class="toolcard ${e.status} ${this.revealed===e.id?`revealed`:``}" data-tool=${i} data-card=${e.id}>
      <div class="th" @click=${()=>{this.openCards.set(e.id,!t),this.requestUpdate()}}>
        <span class="tn">${e.name||N(`tool`)}</span><span class="tp">${e.preview}</span><span class="ti"
          >${n.length===1?N(`1 result`):n.length?N(M`${n.length} results`):e.intent}</span
        >${r}
      </div>
      ${t?O`<div class="tb">${e.webQuery?this.webSearchBody(e,n):e.webFetch?this.webFetchBody(e):this.toolBody(e)}</div>`:k}
    </div>`}toolBody(e){return e.out===null?this.codeBlock(e.cmd,`${e.id}:cmd`):O`${e.cmd?this.codeBlock(e.cmd,`${e.id}:cmd`):k}${this.codeBlock(e.out,`${e.id}:out`)}`}webSearchBody(e,t){return O`<div class="wq"><span class="wl">${N(`query`)}</span><b>${e.webQuery}</b></div>
      ${t.length?O`<ol class="links">
            ${t.map(e=>O`<li><a href=${e.url} target="_blank" rel="noopener noreferrer">${e.title}</a><span class="host">${Wc(e.url)}</span></li>`)}
          </ol>`:k}
      ${e.out===null?k:t.length?O`<details class="rawfold"><summary>${N(`Full text`)}</summary>${this.codeBlock(e.out,`${e.id}:out`)}</details>`:this.codeBlock(e.out,`${e.id}:out`)}`}webFetchBody(e){let t=/^https?:\/\//.test(e.webFetch)?e.webFetch:``;return O`<div class="wq">
        <span class="wl">${N(`page`)}</span>${t?O`<a class="plink" href=${t} target="_blank" rel="noopener noreferrer">${t}</a>`:O`<b>${e.webFetch}</b>`}
      </div>
      ${e.out===null?k:this.codeBlock(e.out,`${e.id}:out`)}`}revealWebSearch(e,t=0){let n=0,r=this.model.rounds.length-1;for(let[i,a]of this.model.rounds.entries())for(let o of a.items)if(o.kind===`tool`&&o.webQuery===e&&n++===t)return this.openCards.set(o.id,!0),this.pinned=null,this.revealed=o.id,this.revealPending=!0,this.requestUpdate(),{round:i===r?null:i+1}}codeBlock(e,t){let n=O`<pre><code>${e.slice(0,Vc)}</code></pre>`;if(e.length<=Bc)return n;let r=this.folds.has(t);return O`<div>
      <div class="fold ${r?`open`:``}">${n}</div>
      <button type="button" class="foldbtn" @click=${()=>{r?this.folds.delete(t):this.folds.add(t),this.requestUpdate()}}>${N(r?`Show less`:M`Show all (${e.length} characters)`)}</button>
    </div>`}typing(){return O`<div class="typing"><span class="av av-a">A</span><span class="dots"><i></i><i></i><i></i></span><span class="meta">${N(`running`)}</span></div>`}};W([H({attribute:!1})],Q.prototype,`events`,void 0),W([H()],Q.prototype,`run`,void 0),W([H({attribute:!1})],Q.prototype,`stream`,void 0),W([H({attribute:`base-url`})],Q.prototype,`baseUrl`,void 0),W([H({attribute:!1})],Q.prototype,`client`,void 0),W([H({type:Boolean})],Q.prototype,`live`,void 0),W([H({attribute:!1})],Q.prototype,`round`,void 0),W([H({attribute:!1})],Q.prototype,`rows`,void 0),W([H({reflect:!0})],Q.prototype,`mode`,void 0),W([U()],Q.prototype,`version`,void 0),W([U()],Q.prototype,`behind`,void 0),W([U()],Q.prototype,`bulk`,void 0),W([U()],Q.prototype,`unseen`,void 0),W([U()],Q.prototype,`pinned`,void 0),W([U()],Q.prototype,`revealed`,void 0),W([Xn(`.scroller`)],Q.prototype,`scroller`,void 0),Q=W([V(`ca-transcript`),P()],Q);var Gc=()=>({transcript:N(`Transcript`),input:N(`Input`),output:N(`Output`),definition:N(`Definition`)}),Kc=e=>Ai((e.rounds||1)-1),qc=new Set([`key`,`rows`,`launches`,`stream`,`task_detail_error`,`definition`,`io`]),Jc=e=>({key:e,rows:[],launches:[],definition:null,io:{params:{},inputs:[],outputs:[],executor:`agent`,upstream:[],downstream:[]},stream:null}),Yc=(e,t=e)=>O`<span class="pill p-${e}">${t}</span>`,Xc={done:`completed`,attention:`invalid_input`,muted:`skipped`,running:`running`,failed:`error`},Zc=e=>typeof e==`string`?e:JSON.stringify(e)??String(e),Qc=(e,t)=>{try{return JSON.stringify(e)===JSON.stringify(t)}catch{return!1}},$c=e=>O`<span aria-hidden="true">${e?`✓`:`✕`}</span><span class="sr">${N(e?`passed`:`failed`)}</span>`,$=class extends A{constructor(...e){super(...e),this.baseUrl=``,this.run=``,this.taskKey=null,this.view=`transcript`,this.round=null,this.live=!1,this.journal=[],this.plan=null,this.detail=null,this.launches=[],this.shownRound=-1,this.rounds=[],this.token=0,this.outcomes=new Map,this.producerOf=e=>{let t=this.writerOf(e);if(!t)return;let n=t.outputs.find(t=>t.path===e);return{name:L(t),written:!!n?.file.exists,outcome:this.outcomes.get(t.key)?.outcome}}}static{this.styles=[B,Zo,Rc,c`
      :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
      .taskmeta { flex: none; background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
        border-radius: 14px; padding: 10px 12px; margin-bottom: 8px; color: var(--text-2); }
      .tm-head { display: flex; gap: 12px; align-items: center; }
      .tm-av { width: 36px; height: 36px; border-radius: 11px; display: grid; place-items: center; font-size: 16px; flex: none;
        background: var(--agent-bg); color: var(--agent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--agent) 35%, transparent); }
      .tm-av.py { background: var(--raise); color: var(--text-muted); box-shadow: none; }
      .tm-name { font-size: 15px; font-weight: 600; color: var(--text); display: flex; gap: 8px; align-items: center; }
      .verdict { font-size: 12.5px; color: var(--text); margin-top: 2px; }
      .verdict.failed { color: var(--status-failed); }
      .verdict.attention { color: var(--status-attention); }
      .verdict.mut { color: var(--text-muted); }
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
    `]}willUpdate(e){(e.has(`run`)||e.has(`taskKey`)||e.has(`client`))&&this.fetch(),this.outcomes=this.plan?Qr(this.journal,this.plan):new Map}async fetch(){let e=++this.token;this.detail=null,this.launches=[],this.shownRound=-1,this.rounds=[];let{run:t,taskKey:n}=this;if(!t||!n||!this.client)return;let r;try{r=await this.client.task(t,n)}catch{r=Jc(n)}e===this.token&&(this.detail=r)}openTask(e,t){e.preventDefault(),j(this,`ca-open-task`,{key:t})}isPy(e){return G(e.io)||e.rows.some(G)}hadSession(e){return!this.isPy(e)&&(!!e.stream||e.launches.length>0||e.rows.some(K))}shownView(e){return this.view===`transcript`&&this.isPy(e)&&!e.stream?`output`:this.view}stateOf(e,t){return t?`running`:bi(e.rows,this.outcomes.get(e.key))}writerOf(e){return this.detail?.io.upstream.find(t=>t.outputs.some(t=>t.path===e))}notStartedCause(e){let t=Li(this.outcomes.get(e.key)??{attempts:e.rows,cause:null},this.outcomes,this.run,e=>this.writerOf(e)?.key);if(t)return t;let n=Fi(e.rows[e.rows.length-1]?.reason)[0],r=n?this.writerOf(n.path):void 0;return n?Ii(J(n.path,this.run),n.problem,r?{name:L(r)}:void 0):``}culprit(e){let t=Fi(e.rows[e.rows.length-1]?.reason)[0],n=t?.producer?this.outcomes.get(t.producer):void 0;if(n)return n;let r=t?this.writerOf(t.path):void 0;if(r)return r;let i=this.outcomes.get(e.key)?.cause;return i?this.outcomes.get(i):void 0}link(e){return O`<a class="lnk" href="#" @click=${t=>this.openTask(t,e.key)}>${L(e)}</a>`}render(){let e=this.taskKey;if(!e)return O`<div class="blank"><span class="ic" aria-hidden="true">✦</span><b>${N(`No task selected`)}</b></div>`;let t=this.detail;if(!t)return O`<div class="taskmeta meta"><strong>${e}</strong> ${N(`Loading…`)}</div>`;let n=t.launches.length>0&&this.live,r=this.shownView(t);return O`${this.renderMeta(e,t,n)} ${this.renderViews(t,r)}
      ${t.stream?O`<ca-transcript .run=${this.run} .stream=${t.stream} base-url=${this.baseUrl} .client=${this.client} .live=${n}
            .rows=${t.rows} .round=${this.round} mode=${r===`transcript`?`full`:r===`input`?`tabs`:`none`}
            @rounds-changed=${e=>{this.launches=e.detail.launches,this.shownRound=e.detail.shown,this.rounds=e.detail.rounds}}></ca-transcript>`:r===`transcript`?this.noTranscript(t,n):k}
      ${r===`transcript`?k:O`<div class="pane">${this.renderPane(t,r,n)}</div>`}`}noTranscript(e,t){let n=this.stateOf(e,t);if(n===`not_started`){let t=this.culprit(e);return O`<div class="blank notrans"><span class="ic" aria-hidden="true">⊘</span><b>${I(N(`No transcript`),_i(n))}</b>
        ${t?O`<span>${N(`Earlier task`)} ${lo(this,L(t),t)}</span>`:k}</div>`}return this.hadSession(e)?O`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${N(`No transcript`)}</b>
        <span>${N(`Transcript not saved (keep_transcripts = false)`)}</span></div>`:O`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${I(N(`No transcript`),_i(n))}</b></div>`}verdict(e,t){let n=e.rows,r=n.filter(K),i=n[n.length-1],a=this.stateOf(e,t);switch(a){case`running`:return[N(`Running`),``];case`waiting`:return[N(`Waiting`),`mut`];case`skipped`:return[N(`Skipped`),`mut`];case`not_started`:{let t=this.notStartedCause(e);return[N(t?M`Not started: ${t}`:`Not started`),`attention`]}case`failed`:{let e=J(i?.reason,this.run)||q(i?.stop);return[r.length>1?N(M`Failed on all ${r.length} attempts: ${e}`):N(M`Failed: ${e}`),`failed`]}}if(!i)return[_i(a),``];let o=r.filter(e=>!e.ok);if(o.length){let e=J(o[0]?.reason,this.run)||q(o[0]?.stop);return[o.length===1?N(M`Done on attempt ${r.length} after 1 failed attempt. First failure: ${e}`):N(M`Done on attempt ${r.length} after ${o.length} failed attempts. First failure: ${e}`),``]}let s=(i.rounds||1)-1+(i.hook_errors??[]).length;if(s>0){let e=[...(i.hook_errors??[]).flat(),...(i.round_errors??[]).flat(),...this.rounds.flatMap(e=>e.rejectedWith)],t=e[0]?jc(J(e[0],this.run)):``;return t?[N(s===1?M`Done after 1 correction. First failed check: ${t}`:M`Done after ${s} corrections. First failed check: ${t}`),``]:[N(s===1?`Done after 1 correction`:M`Done after ${s} corrections`),``]}let c=Pi(i.hops);return c?[N(M`Done after a model switch: ${c}`),``]:[N(`Done`),``]}streamModel(){for(let e=this.launches.length-1;e>=0;e--){let t=this.launches[e],n=t?vc(t).model:``;if(n)return n}return``}renderMeta(e,t,n){let{rows:r,launches:i}=t,a=this.isPy(t),o=this.hadSession(t),s=r.slice().sort((e,t)=>String(e.ts).localeCompare(String(t.ts))),c=s[s.length-1],l=i[0],u={agent:gc(l?.cmd?l.cmd.split(` `)[0]:c?.agent),model:l?.model||c?.model||this.streamModel(),role:l?.role||``},d=o?[...new Set(s.map(e=>e.model).filter(e=>!!e&&e!==u.model))]:[],f=r[0],p=r.filter(K),m=Object.entries(t).filter(([e])=>!qc.has(e)),[h,g]=this.verdict(t,n),_=N(a?`Python task`:`Agent task`),v=this.plan?.nodes.find(e=>e.key===t.key);return O`<div class="taskmeta">
      <div class="tm-head">
        <span class="tm-av ${a?`py`:``}" title=${_}><span aria-hidden="true">${a?`⚙`:`✦`}</span><span class="sr">${_}</span></span>
        <div style="min-width:0">
          <div class="tm-name" title=${e}>${f?L(f):v?L(v):e.replace(/^python:/,``)} ${n?Yc(`running`,N(`running`)):k}</div>
          <div class="verdict ${g}">${h}</div>
          ${o?O`<div class="whos">
                ${Lc(u)}${this.identityChip(p)}
                ${d.length?O`<span class="meta">${d.length===1?N(M`Earlier attempts used model ${d[0]??``}`):N(M`Earlier attempts used models ${d.join(`, `)}`)}</span>`:k}
              </div>`:k}
          ${i.length?O`<div class="meta">${i.length===1?N(`1 agent session running`):N(M`${i.length} agent sessions running`)}</div>`:k}
          ${this.spendLine(ci(r))}
          ${this.quotaLine(p)}
        </div>
      </div>
      ${p.length?O`<div class="runchips">${wi(p).map((e,t)=>this.runChip(p[t],e,o))}</div>`:k}
      ${this.searchFold(p)}
      ${Dn(p)?O`<div class="meta unread" title=${N(`Event types from the coding agent that this contraagent version does not recognize`)}>
            <span aria-hidden="true">⚠</span> ${N(M`Unrecognized events: ${Dn(p)}`)}
          </div>`:k}
      ${t.task_detail_error?O`<div class="meta v-bad">${N(M`The task_detail callback failed: ${t.task_detail_error??``}`)}</div>`:k}
      ${i.map(e=>O`<details class="launch">
          <summary>${I(N(M`Process ${e.pid??`—`}`),e.key||``)}</summary>
          <div class="meta">${I(N(M`Plugin ${e.plugin||N(`none`)}`),N(M`Model ${e.model||`—`}`),N(M`Role ${e.role||N(`none`)}`))}</div>
        </details>`)}
      ${m.map(([e,t])=>O`<details class="io-fold"><summary>${e}</summary><ca-json-tree .value=${t}></ca-json-tree></details>`)}
    </div>`}identityChip(e){let t=[...new Set(e.flatMap(e=>[...(e.hops??[]).map(e=>e.credential),e.credential]).filter(e=>!!e))];return t.length?O`<span class="who ident" title=${[N(`What the coding agent authenticated as: an account or an API key (credential)`),...t.map(Mi)].filter(Boolean).join(`
`)}
          ><span class="who-l">${N(`identity`)}</span>${t.map(ji).join(`, `)}</span
        >`:k}searchFold(e){let t=e.flatMap(e=>e.web_queries??[]),n=new Map;return t.length?O`<details class="io-fold">
          <summary>${t.length===1?N(`1 web search`):N(M`${t.length} web searches`)}</summary>
          <ol class="meta searches">
            ${t.map(e=>{let t=n.get(e)??0;return n.set(e,t+1),O`<li><button class="qlink jmono" @click=${()=>this.revealSearch(e,t)}>
                ${e}
              </button></li>`})}
          </ol>
        </details>`:k}revealSearch(e,t){let n=this.transcriptEl?.revealWebSearch(e,t);j(this,`ca-navigate`,n?{view:`transcript`,round:n.round}:{view:`transcript`})}spendLine(e){return e?O`<div class="spend">
      <b title=${N(`Reported by the coding agent`)}>${En(e.cost)}</b>
      <span>${N(M`Tokens: ${z(e.input)} input, ${z(e.output)} output, ${z(e.cache_read)} cache read, ${z(e.cache_creation)} cache write`)}</span>
      <span>${e.calls===1?N(`1 API call`):N(M`${e.calls} API calls`)}</span>
    </div>`:k}quotaLine(e){let t=mi(this.journal.length?this.journal:e),n=e[0],r=e[e.length-1],i=n?gi(n,t).start:null;if(!i||!r)return k;let a=gi(r,t).next;return O`<div class="spend quota">
      <span title=${ao(i)}>${N(M`Usage at session start: ${io(i)}`)}</span>
      ${a?O`<span title=${ao(a)}>${N(M`Usage after this task: ${io(a)}`)}</span>`:k}
    </div>`}runChip(e,t,n){let r=e.ok,i=J(e.reason,this.run),a=Pi(e.hops),o=[N(M`Ended ${Sn(e.ts,!0)}`),Kc(e),n&&e.model?N(M`Model ${e.model}`):``,a?N(M`Model switch: ${a}`):``,i,e.route||``].filter(Boolean).join(`
`),s=e.cost_usd!==null&&e.cost_usd!==void 0?En(e.cost_usd):``;return O`<span class="runchip ${r?`ok`:`bad`}" title=${o}>
      ${$c(r)} ${I(t,q(e.stop,e.reason),F(e.wall_s),s)}
    </span>`}renderViews(e,t){let n=e.io,r=this.isPy(e)&&!e.stream,i={input:new Set([...n.inputs.map(e=>e.path),...n.upstream.flatMap(e=>e.outputs.map(e=>e.path))]).size+Object.keys(n.params).length,output:n.outputs.length};return O`<div class="tviews" role="tablist">
      ${ct.filter(e=>!(r&&e===`transcript`)).map(e=>{let n=Gc()[e];return O`<button type="button" role="tab" aria-selected=${e===t} class="tview ${e===t?`sel`:``}"
          @click=${()=>j(this,`ca-navigate`,{view:e})}>
          ${n}${i[e]?O`<span class="badge">${i[e]}</span>`:k}
        </button>`})}
    </div>`}renderPane(e,t,n){return t===`input`?this.inputPane(e,n):t===`output`?this.outputPane(e):O`<ca-definition .definition=${e.definition??null} memory="task-definition"></ca-definition>`}inputPane(e,t){let n=e.io,r=Object.entries(n.params),{files:i,earlier:a}=uc(n),o=e=>n.upstream.find(t=>t.outputs.some(t=>t.file.exists&&Qc(t.file.content,e)));return O`<h4 class="sect-h">${N(`Parameters`)}</h4>
      ${r.length?O`<table class="ct-fields params">
            ${r.map(([e,t])=>{let n=o(t);return O`<tr>
                <td class="jmono">${e}</td>
                <td>${typeof t==`object`&&t?O`<ca-json-tree .value=${t} .open=${0}></ca-json-tree>`:O`<span class="jmono">${Zc(t)}</span>`}</td>
                <td>${n?O`<span class="from">${N(O`From ${this.link(n)}`)}</span>`:k}</td>
              </tr>`})}
          </table>`:O`<div class="meta">${N(`No parameters`)}</div>`}
      <h4 class="sect-h">${N(`Input files`)}</h4>
      ${i.length?i.map(e=>this.inputCard(e)):O`<div class="meta">${N(`No input files`)}</div>`}
      <h4 class="sect-h">${N(`Earlier tasks`)}</h4>
      ${a.length?a.map(e=>this.earlierTask(e)):O`<div class="meta">${N(`No earlier tasks`)}</div>`}
      ${this.isPy(e)?k:this.promptSection(e,t)}`}inputCard(e){let t=e.from,n=t?this.outcomes.get(t.key)?.outcome:void 0,r=t?O`<span>${N(O`Output of ${this.link(t)}`)}</span>${n&&n!==`done`?O`<span class="pill o-${n}">${_i(n)}</span>`:k}`:N(`File from before the run`),i=e.out?.status;if(!i)return Xo(e.spec,`input`,this.run,{origin:r});let a=O`<span class="ct-chip ${i}" title=${jo(i)}>${Ao(i)}</span>`;return Xo({...e.spec,status:i},`input`,this.run,{origin:r,chip:a})}earlierTask(e){let t=e.task,n=G(t)?N(`Python task`):N(`Agent task`),r=this.outcomes.get(t.key)?.outcome,i=t.outputs.length,a=i?I(N(i===1?`1 output file`:M`${i} output files`),e.read?e.read===1?N(`1 read by this task`):N(M`${e.read} read by this task`):``):N(`No output files`),o=O`<div class="up-hd">
      <span class="k-ic ${G(t)?``:`llm`}" title=${n}><span aria-hidden="true">${G(t)?`⚙`:`✦`}</span><span class="sr">${n}</span></span>
      ${this.link(t)}
      ${r?O`<span class="pill o-${r}">${_i(r)}</span>`:k}
      <span class="meta">${a}</span>
    </div>`;if(!e.rest.length)return O`<div class="upstream">${o}</div>`;let s=e.rest.map(e=>Xo(e,`output`,this.run,{producerOf:this.producerOf}));return e.rest.some(lc)?O`<div class="upstream">${o}${s}</div>`:O`<details class="upstream"><summary>${o}</summary>${s}</details>`}promptSection(e,t){let n=this.launches.length,r=this.shownRound,i=this.rounds[r],a=this.rounds[this.rounds.length-1]?.tryNo??1,o=e.rows.filter(K),s=wi(o),c=Ur(o),l=this.launches[r]?.prompt??``,u=this.stateOf(e,t);return O`<h4 class="sect-h">${N(`Prompt`)}${n>1&&i?O` <span class="meta">${dc(i,a,s[i.tryNo-1])}: ${fc(i,c[i.tryNo-1]!==c[i.tryNo-2])}</span>`:k}</h4>
      ${l?O`<ca-markdown .text=${l}></ca-markdown>`:O`<div class="meta">${e.stream?N(`Loading…`):this.hadSession(e)?N(`Prompt not saved (keep_transcripts = false)`):I(N(`No prompt`),_i(u))}</div>`}`}usageTable(e){let t=e.filter(e=>K(e)&&(e.usage||e.cost_usd!==null&&e.cost_usd!==void 0));if(!t.length)return k;let n=O`<td class="jdim">—</td>`,r=mi(this.journal.length?this.journal:e),i=t.some(e=>(e.quota??[]).length),a=O`<td class="l jdim">—</td>`,o=(e,t)=>e?O`<td class="l" title=${ao(e)}>${(e.credential??``)===(t??``)?io(e):oo(e)}</td>`:a;return O`<h4 class="sect-h">${N(`Tokens and cost`)}</h4>
      <div class="usage-wrap"><table class="usage">
        <tr>
          <th class="l"></th><th>${N(`Input`)}</th><th>${N(`Output`)}</th><th>${N(`Cache read`)}</th><th>${N(`Cache write`)}</th>
          <th>${N(`API calls`)}</th><th title=${N(`Reported by the coding agent`)}>${N(`Cost`)}</th><th class="l">${N(`Identity`)}</th>
          ${i?O`<th class="l" title=${N(`Subscription usage when the agent session started (account-wide)`)}>${N(`Usage at start`)}</th>
                <th class="l" title=${N(`The first reading of the same account after this attempt ended`)}>${N(`Usage after`)}</th>`:k}
        </tr>
        ${t.map(e=>{let t=e.usage,a=e.hops??[];return O`<tr>
              <td class="l">${Ci(e.attempt)}</td>
              ${t?O`<td>${z(t.input)}</td><td>${z(t.output)}</td><td>${z(t.cache_read)}</td><td>${z(t.cache_creation)}</td><td>${t.calls}</td>`:O`${n}${n}${n}${n}${n}`}
              <td>${En(e.cost_usd)}</td><td class="l" title=${Mi(e.credential)||k}>${ji(e.credential)||`—`}</td>
              ${i?O`${o(gi(e,r).start,e.credential)}${o(gi(e,r).next,e.credential)}`:k}
            </tr>
            ${a.length>1?a.map(e=>O`<tr class="hop">
                    <td class="l">${I(e.model||e.route||`—`,q(e.stop))}</td>
                    <td></td><td></td><td></td><td></td><td></td>
                    <td>${En(e.cost_usd)}</td><td class="l" title=${Mi(e.credential)||k}>${ji(e.credential)||`—`}</td>
                    ${i?O`<td></td><td></td>`:k}
                  </tr>`):k}`})}
      </table></div>`}outputPane(e){let t=e.io,n=e.rows[e.rows.length-1];return O`<h4 class="sect-h">${N(`Output files`)}</h4>
      ${t.outputs.length?t.outputs.map(e=>Xo(e,`output`,this.run,{producerOf:this.producerOf})):O`<div class="meta">${N(`No output files`)}</div>`}
      ${n?O`<h4 class="sect-h">${N(`Outcome`)}</h4>
            <div class="ct-in">
              ${Yc(Xc[Ui(n.stop)]??`error`,q(n.stop,n.reason))}
              ${K(n)?O`<span class="meta">${I(Ci(n.attempt),F(n.wall_s),Kc(n))}</span>`:k}

            </div>`:k}
      ${this.usageTable(e.rows)}
      <h4 class="sect-h">${N(`Later tasks`)}</h4>
      ${t.downstream.length?O`<div class="down">${t.downstream.map(e=>lo(this,L(e),e))}</div>`:O`<div class="meta">${N(`No later tasks`)}</div>`}`}};W([H({attribute:!1})],$.prototype,`client`,void 0),W([H({attribute:`base-url`})],$.prototype,`baseUrl`,void 0),W([H()],$.prototype,`run`,void 0),W([H({attribute:!1})],$.prototype,`taskKey`,void 0),W([H()],$.prototype,`view`,void 0),W([H({attribute:!1})],$.prototype,`round`,void 0),W([H({type:Boolean})],$.prototype,`live`,void 0),W([H({attribute:!1})],$.prototype,`journal`,void 0),W([H({attribute:!1})],$.prototype,`plan`,void 0),W([U()],$.prototype,`detail`,void 0),W([Xn(`ca-transcript`)],$.prototype,`transcriptEl`,void 0),W([U()],$.prototype,`launches`,void 0),W([U()],$.prototype,`shownRound`,void 0),W([U()],$.prototype,`rounds`,void 0),$=W([V(`ca-task-view`),P()],$);var el=()=>[{id:`overview`,label:N(`Overview`),icon:`◎`},{id:`tasks`,label:N(`Tasks`),icon:`≡`},{id:`journal`,label:N(`History`),icon:`▤`,tip:`journal.jsonl`},{id:`outputs`,label:N(`Outputs`),icon:`▣`},{id:`definitions`,label:N(`Definitions`),icon:`⌘`},{id:`procs`,label:N(`Processes`),icon:`⚙`},{id:`stream`,label:N(`Task detail`),icon:`✦`}],tl=250,nl=class extends A{constructor(){super(),new nr(this)}createRenderRoot(){return this}render(){return new Date().toLocaleTimeString(mn(),{hour12:!1})}};nl=W([V(`ca-clock`),P()],nl);var rl=class extends A{constructor(...e){super(...e),this.baseUrl=``,this.history=`url`,this.run=``,this.locale=``,this.theme=``,this.live=!1,this.pickerOpen=!1,this.qDraft=null,this.light=nt(),this.mainScroll=new Bi(`main`),this.pendingScroll=null,this.qTimer=null,this.cleanups=[]}static{this.styles=[it,B,c`
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
      .hdr-right { margin-left: auto; display: flex; align-items: center; gap: 12px; min-width: 0; }
      .nowline { font-size: 12px; color: var(--text-2); white-space: nowrap; overflow: hidden; max-width: 40vw;
        display: inline-flex; align-items: center; gap: 4px; }
      .clock { font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); }
      .langs { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; overflow: hidden; }
      .langs button { background: none; border: 0; padding: 2px 9px; font-size: 11px; color: var(--text-muted); cursor: pointer; }
      .langs button:hover { color: var(--text-2); }
      .langs button[aria-pressed='true'] { background: var(--raise); color: var(--text); }
      .live-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--status-running); display: inline-block; animation: breathe 1.8s ease-in-out infinite; }
      .live-dot.off { background: var(--line2); animation: none; box-shadow: none; }

      nav { flex: none; display: flex; gap: 2px; padding: 6px 18px 0; position: relative; overflow-x: auto; scrollbar-width: none; align-items: center; }
      nav::-webkit-scrollbar { display: none; }
      .tab { position: relative; background: none; border: none; padding: 8px 14px 11px; color: var(--text-muted); cursor: pointer;
        font-weight: 500; white-space: nowrap; transition: color 0.2s; }
      .tab:hover { color: var(--text-2); }
      .tab.sel { color: var(--text); }
      .tab-ic { opacity: 0.55; margin-right: 6px; font-size: 12px; }
      .tab.sel .tab-ic { opacity: 1; color: var(--accent); }
      .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--text-2); font-variant-numeric: tabular-nums; }
      .badge.running { background: var(--status-running-bg); color: var(--status-running); }
      .tab-sep { width: 1px; height: 18px; background: var(--line2); margin: 0 8px 3px; flex: none; align-self: center; }
      .tab-ind { position: absolute; bottom: 0; left: 0; width: 0; height: 2px; border-radius: 2px;
        background: var(--accent); transition: left 0.3s var(--ease), width 0.3s var(--ease); }
      .tab-ind.init { transition: none; }
      .tabhint { margin-left: auto; padding-left: 12px; white-space: nowrap; }

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
    `]}connectedCallback(){super.connectedCallback(),hn(_n(this.locale)?this.locale:vn()),this.applyTheme();let e=globalThis.matchMedia?.(`(prefers-color-scheme: light)`);if(e){let t=e=>this.light=e.matches;e.addEventListener(`change`,t),this.cleanups.push(()=>e.removeEventListener(`change`,t))}this.store=new Yr({baseUrl:this.baseUrl}),this.snap=this.store.snapshot,this.cleanups.push(this.store.subscribe(e=>{this.snap=e,this.pickDefaultRun()}),this.store.onNewRow(e=>this.announce(e))),this.router=new kt(this.history,(e,t)=>this.onRoute(e,t),this.run?{run:this.run}:{}),this.router.start(),this.store.start();let t=e=>this.onKey(e),n=e=>{this.pickerOpen&&!e.composedPath().some(e=>e instanceof HTMLElement&&(e.localName===`ca-run-picker`||e.classList.contains(`runbtn`)))&&(this.pickerOpen=!1)},r=()=>this.moveTabIndicator();document.addEventListener(`keydown`,t),document.addEventListener(`click`,n),addEventListener(`resize`,r),this.cleanups.push(()=>document.removeEventListener(`keydown`,t),()=>document.removeEventListener(`click`,n),()=>removeEventListener(`resize`,r)),this.addEventListener(`ca-open-task`,e=>{this.navigate({tab:`stream`,key:e.detail.key,...e.detail.view?{view:e.detail.view}:{}})}),this.addEventListener(`ca-navigate`,e=>{let{replace:t,...n}=e.detail;this.navigate(n,{replace:t===!0})}),this.addEventListener(`ca-select-run`,e=>this.navigate({run:e.detail.run})),this.addEventListener(`ca-filter`,e=>this.navigate(e.detail)),this.addEventListener(`ca-choose-theme`,e=>{this.theme=e.detail.theme,tt(e.detail.theme)})}themeChoice(){return Xe(this.theme)?this.theme:et()}get shownTheme(){return Ze(this.themeChoice(),this.light)}applyTheme(){let e=this.shownTheme;this.getAttribute(`data-ca-theme`)!==e&&this.setAttribute(`data-ca-theme`,e),this.history===`url`&&document.documentElement.getAttribute(`data-ca-theme`)!==e&&document.documentElement.setAttribute(`data-ca-theme`,e)}disconnectedCallback(){super.disconnectedCallback();for(let e of this.cleanups.splice(0))e();this.router.stop(),this.store.stop(),this.mainScroll.detach()}navigate(e,t={}){this.router.navigate(e,t)}onRoute(e,t){this.route=e,t!==`replace`&&(this.qDraft=null),this.store.selectRun(e.run),this.pickDefaultRun(),t!==`replace`&&(this.pendingScroll=t)}pickDefaultRun(){let e=this.snap.runs[0];!this.route.run&&e&&this.navigate({run:e.run},{replace:!0})}announce(e){let t=L(e),n=J(e.reason,this.snap.run).slice(0,110);e.stop===`invalid_input`?this.toasts?.show(`attention`,N(M`${t}: not started`),n):Hr(e)?this.toasts?.show(`failed`,N(M`${t}: ${q(e.stop)}`),n):(e.hops||[]).length>1?this.toasts?.show(`agent`,N(M`${t}: model switch`),Pi(e.hops,e.wall_s).slice(0,110)):this.toasts?.show(`done`,N(M`${t}: done`),I(F(e.wall_s),e.model))}tabs(){return[...el().map(e=>({...e,panel:!1})),...this.snap.info.panels.map(e=>({id:`panel:${e.name}`,label:e.title||e.name,icon:e.icon||`▤`,tip:e.description?N(M`${e.description} (custom view)`):N(`Custom view`),panel:!0}))]}onKey(e){let t=e.composedPath()[0];if(!(t instanceof HTMLElement&&t.matches(`input, select, textarea`)||e.metaKey||e.ctrlKey||e.altKey)){if(e.key===`r`)e.preventDefault(),this.pickerOpen=!0;else if(e.key===`/`)e.preventDefault(),this.renderRoot.querySelector(`.bar input`)?.focus();else if(/^[1-9]$/.test(e.key)){let t=this.tabs()[Number(e.key)-1];t&&this.navigate({tab:t.id})}}}willUpdate(e){e.has(`snap`)&&(this.live=Kr(this.snap.state,Gr(this.snap.runs,this.snap.run)),document.title=N(M`${this.snap.info.title} monitor`))}updated(e){e.has(`locale`)&&_n(this.locale)&&this.locale!==mn()&&hn(this.locale),this.history===`url`&&(document.documentElement.lang=mn()),this.lang=mn(),this.applyTheme(),this.moveTabIndicator(),this.main&&this.mainScroll.attach(this.main),this.pendingScroll&&=(this.pendingScroll===`push`?this.mainScroll.reset():this.mainScroll.restore(),null)}moveTabIndicator(){let e=this.renderRoot.querySelector(`.tab.sel`),t=this.renderRoot.querySelector(`.tab-ind`);e&&t&&(t.style.left=`${e.offsetLeft+10}px`,t.style.width=`${Math.max(12,e.offsetWidth-20)}px`,t.classList.contains(`init`)&&requestAnimationFrame(()=>t.classList.remove(`init`)))}setQ(e){this.qDraft=e,this.qTimer&&clearTimeout(this.qTimer),this.qTimer=setTimeout(()=>{this.qTimer=null,this.navigate({q:e})},tl)}runLine(e){let t=qi(e),n=this.snap.state.ready?ci(this.snap.state.journal)?.cost:e.cost_usd,r=n==null?``:En(n),i=so(this.accounts(e)),a=I(t==null?``:N(M`took ${F(t)}`),r,i,e.running?N(`running`):``);if(!this.snap.state.ready)return a;let o=ei(Qr(this.snap.state.journal,this.snap.state.plan));return I(N(M`${o.done+o.recovered} of ${o.total} tasks done`),a)}accounts(e){return this.snap.state.ready?hi(this.snap.state.journal):e.quota??[]}triesLine(){let{tries:e,notStarted:t}=Gi(this.snap.state.journal);return I(N(e===1?`1 attempt`:M`${e} attempts`),t?Si(`not_started`,t):``)}pickLocale(e){this.locale=e,yn(e)}render(){if(!this.snap||!this.route)return k;let{snap:e,route:t}=this,n=Gr(e.runs,e.run),r=qr(e.state.procs),i=n?.tasks,a=Hi(!!n?.running,i);return O`
      <header>
        <div class="brand">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle class="logo-ring" cx="12" cy="12" r="9.5" fill="none" stroke-width="1.5" stroke-dasharray="4 3" />
            <circle class="logo-core" cx="12" cy="12" r="4" />
          </svg>
          <span>${e.info.title}</span>
        </div>
        <button type="button" class="runbtn" title=${N(`Switch run (r)`)} @click=${()=>this.pickerOpen=!this.pickerOpen}>
          <span class="dot ${a}" aria-hidden="true"></span>
          <span class="rn">${t.run||`—`}</span>
          <span class="rs" title=${n?co(this.accounts(n)):``}>${n?this.runLine(n):``}</span>
          <span class="chev" aria-hidden="true">▾</span>
        </button>
        <div class="hdr-right">
          <span class="nowline">${r.length?O`${N(`Running`)} ${r.slice(0,3).map(e=>lo(this,L(e),{key:e.key}))}${r.length>3?O` <span>+${r.length-3}</span>`:k}`:k}</span>
          <ca-theme-switch .value=${this.themeChoice()} .system=${Ze(`system`,this.light)}></ca-theme-switch>
          <span class="langs" role="group" aria-label=${N(`Language`)}>
            ${ln.map(e=>O`<button type="button" lang=${e} aria-pressed=${e===mn()} @click=${()=>this.pickLocale(e)}>
                ${fn[e]}
              </button>`)}
          </span>
          <span title=${e.connected?N(`Connected to the monitor server`):N(`Not connected to the monitor server`)}
            ><span class="live-dot ${e.connected?``:`off`}"></span><span class="sr">${e.connected?N(`Connected to the monitor server`):N(`Not connected to the monitor server`)}</span></span
          >
          <ca-clock class="clock"></ca-clock>
        </div>
        <ca-run-picker style="left:110px" .runs=${e.runs} current=${t.run} ?open=${this.pickerOpen}
          @close=${()=>this.pickerOpen=!1}></ca-run-picker>
      </header>
      ${this.renderTabs(r.length)} ${this.renderBar()}
      <main class=${t.tab===`stream`?`stream`:``}>${this.renderView()}</main>
      <ca-toasts></ca-toasts>
    `}renderTabs(e){let{state:t}=this.snap,{tries:n}=Gi(t.journal),r=ei(Qr(t.journal,t.plan)),i=i=>i===`tasks`?[r.total||``,``]:i===`journal`?[n||``,``]:i===`procs`?[t.procs?.alive&&e||``,`running`]:null,a=this.tabs();return O`<nav>
      ${a.map((e,t)=>{let n=i(e.id);return O`${e.panel&&!a[t-1]?.panel?O`<span class="tab-sep" title=${N(`Custom views`)}></span>`:k}
          <button type="button" class="tab ${e.panel?`panel-tab`:``} ${e.id===this.route.tab?`sel`:``}" title=${e.tip??k}
            @click=${()=>this.navigate({tab:e.id})}>
            <span class="tab-ic" aria-hidden="true">${e.icon}</span>${e.label}${n&&n[0]!==``?O`<span class="badge ${n[1]}">${n[0]}</span>`:k}
          </button>`})}
      <span class="tab-ind init"></span>
      <span class="tabhint meta" role="note" aria-label=${N(`Keyboard shortcuts`)}
        ><span aria-hidden="true"><span class="kbd">1</span>–<span class="kbd">${Math.min(9,a.length)}</span> ${N(`Tabs`)} |
          <span class="kbd">r</span> ${N(`Runs`)} | <span class="kbd">/</span> ${N(`Filter`)}</span></span
      >
    </nav>`}renderBar(){let{route:e}=this;if(e.tab!==`tasks`&&e.tab!==`journal`)return k;let{state:t}=this.snap,n=Qr(t.journal,t.plan),r=ei(n).total,i=[...new Set([...n.values()].map(e=>e.kind))].sort();return O`<div class="bar">
      <select title=${N(`Kind`)} aria-label=${N(`Kind`)} @change=${e=>this.navigate({kind:e.target.value})}>
        <option value="" ?selected=${!e.kind}>${N(`All kinds`)}</option>
        ${i.map(t=>O`<option ?selected=${t===e.kind}>${t}</option>`)}
      </select>
      <input placeholder=${N(`Filter`)} aria-label=${N(`Text filter`)} size="22" title=${N(`Text filter (/)`)} .value=${this.qDraft??e.q}
        @input=${e=>this.setQ(e.target.value)} />
      <span class="meta">${e.tab===`journal`?this.triesLine():N(r===1?`1 task`:M`${r} tasks`)}</span>
    </div>`}renderView(){let{snap:e,route:t}=this,{state:n}=e;if(!t.run)return O`<div class="blank"><span class="ic" aria-hidden="true">✦</span><b>${N(`No runs yet`,{id:`no-runs-yet`})}</b></div>`;let r=Gr(e.runs,e.run),i=Kr(n,r),a=this.qDraft??t.q;switch(t.tab){case`overview`:return O`<ca-overview .state=${n} .summary=${r} .info=${e.info} .run=${t.run} .layer=${t.layer} .unit=${t.unit} .sel=${t.sel}></ca-overview>`;case`tasks`:return O`<ca-task-table .run=${t.run} .journal=${n.journal} .plan=${n.plan} .kind=${t.kind} .q=${a} ?live=${i}></ca-task-table>`;case`journal`:return O`<ca-journal-table .run=${t.run} .rows=${n.journal} .fresh=${e.fresh} .kind=${t.kind} .stop=${t.stop} .q=${a}></ca-journal-table>`;case`outputs`:return O`<ca-contracts .run=${t.run} .outputs=${n.outputs} .journal=${n.journal} .plan=${n.plan}></ca-contracts>`;case`definitions`:return O`<ca-definitions .client=${this.store.client} .run=${t.run} .journal=${n.journal} .plan=${n.plan} .live=${i}
          .selected=${t.def}></ca-definitions>`;case`procs`:return O`<ca-procs-view .procs=${n.procs}></ca-procs-view>`;case`stream`:return O`<ca-task-view .client=${this.store.client} .journal=${n.journal} .plan=${n.plan} base-url=${this.baseUrl} .run=${t.run}
          .taskKey=${t.key??ii(ri(n.journal,n.plan))} .view=${t.view} .round=${t.round} .live=${i}></ca-task-view>`;default:{let r=t.tab.slice(6);return O`<ca-panel-view .name=${r} .panel=${e.info.panels.find(e=>e.name===r)} .data=${n.panels[r]}></ca-panel-view>`}}}};W([H({attribute:`base-url`})],rl.prototype,`baseUrl`,void 0),W([H()],rl.prototype,`history`,void 0),W([H()],rl.prototype,`run`,void 0),W([H()],rl.prototype,`locale`,void 0),W([H()],rl.prototype,`theme`,void 0),W([H({type:Boolean,reflect:!0})],rl.prototype,`live`,void 0),W([U()],rl.prototype,`snap`,void 0),W([U()],rl.prototype,`route`,void 0),W([U()],rl.prototype,`pickerOpen`,void 0),W([U()],rl.prototype,`qDraft`,void 0),W([U()],rl.prototype,`light`,void 0),W([Xn(`main`)],rl.prototype,`main`,void 0),W([Xn(`ca-toasts`)],rl.prototype,`toasts`,void 0),rl=W([V(`ca-monitor`),P()],rl),typeof document<`u`&&ot(document);