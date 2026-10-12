var e=Object.defineProperty,t=(t,n)=>{let r={};for(var i in t)e(r,i,{get:t[i],enumerable:!0});return n||e(r,Symbol.toStringTag,{value:`Module`}),r};function n(e,t,n){e.dispatchEvent(new CustomEvent(t,{detail:n,bubbles:!0,composed:!0}))}var r=[`overview`,`tasks`,`journal`,`outputs`,`definitions`,`procs`,`stream`],i=[`transcript`,`input`,`output`,`definition`],a=e=>r.includes(e)||/^panel:.+/.test(e),o=e=>i.includes(e);function s(e){let t=new URLSearchParams(e),n=t.get(`tab`)??``,r=t.get(`view`)??``,i=Number(t.get(`round`));return{run:t.get(`run`)??``,tab:a(n)?n:`overview`,key:t.get(`key`)||null,view:o(r)?r:`transcript`,round:Number.isInteger(i)&&i>0?i:null,def:t.get(`def`)||null,kind:t.get(`kind`)??``,stop:t.get(`stop`)??``,q:t.get(`q`)??``,layer:t.get(`layer`)??``,unit:t.get(`unit`)??``}}function c(e){let t=new URLSearchParams;e.run&&t.set(`run`,e.run),e.tab!==`overview`&&t.set(`tab`,e.tab),e.tab===`stream`&&(e.key&&t.set(`key`,e.key),e.view!==`transcript`&&t.set(`view`,e.view),e.round!=null&&t.set(`round`,String(e.round))),e.tab===`definitions`&&e.def&&t.set(`def`,e.def),e.tab===`overview`&&e.layer&&t.set(`layer`,e.layer),e.tab===`overview`&&e.unit&&t.set(`unit`,e.unit),e.kind&&t.set(`kind`,e.kind),e.stop&&t.set(`stop`,e.stop),e.q&&t.set(`q`,e.q);let n=t.toString();return n?`?${n}`:``}function l(e,t){let n={...e,...t};return t.run!==void 0&&t.run!==e.run&&Object.assign(n,{key:null,def:null,round:null,layer:``,unit:``,...t}),t.key!==void 0&&t.key!==e.key&&(t.view===void 0&&(n.view=`transcript`),t.round===void 0&&(n.round=null)),n}function u(e,t){let n=e=>c({...e,kind:``,stop:``,q:``,unit:``});return n(e)!==n(t)}var d=`contraagent`,f=200,p=null,m=``,h=null;function g(){let e=globalThis.history?.state;return e&&typeof e==`object`?e:{}}function _(){let e=g()[d];return e&&typeof e==`object`?e:{}}function v(){let e=_().entry;if(e)return e;let t=Math.random().toString(36).slice(2);return history.replaceState({...g(),[d]:{..._(),entry:t}},``),t}function ee(){h&&clearTimeout(h),h=null;let e=p;p=null,e&&globalThis.history&&_().entry===m&&history.replaceState({...g(),[d]:{..._(),...e}},``)}function te(e){if(globalThis.history)return p&&m===_().entry&&e in p?p[e]:_()[e]}function y(e,t){if(!globalThis.history)return;let n=v();p&&m!==n&&(p=null),m=n,(p??={})[e]=t,h??=setTimeout(ee,f)}function ne(){ee()}globalThis.addEventListener?.(`pagehide`,ne);var b=class{constructor(e){this.id=e,this.items=new Set(te(e)??[])}has(e){return this.items.has(e)}set(e,t){t!==this.items.has(e)&&(t?this.items.add(e):this.items.delete(e),y(this.id,[...this.items]))}},x=class{constructor(e){this.id=e;let t=null;try{t=JSON.parse(globalThis.sessionStorage?.getItem(`${d}:${e}`)??`null`)}catch{}this.items=new Set(Array.isArray(t)?t.filter(e=>typeof e==`string`):[])}has(e){return this.items.has(e)}set(e,t){if(t!==this.items.has(e)){t?this.items.add(e):this.items.delete(e);try{globalThis.sessionStorage?.setItem(`${d}:${this.id}`,JSON.stringify([...this.items]))}catch{}}}},re=class{constructor(e,t,n){this.mode=e,this.onChange=t,this.onPop=()=>{this.current=s(location.search),this.onChange(this.current,`pop`)};let r=s(e===`url`?location.search:``);this.current=l(r,n??{})}get route(){return this.current}start(){this.mode===`url`&&(history.scrollRestoration=`manual`,addEventListener(`popstate`,this.onPop)),this.onChange(this.current,`init`)}stop(){this.mode===`url`&&removeEventListener(`popstate`,this.onPop)}navigate(e,t={}){let n=l(this.current,e);if(c(n)===c(this.current))return;let r=!t.replace&&u(this.current,n);if(this.current=n,this.mode===`url`){let e=`${location.pathname}${c(n)}${location.hash}`;r?(ne(),history.pushState({},``,e)):history.replaceState(history.state,``,e)}this.onChange(n,r?`push`:`replace`)}},ie=`lit-localize-status`,S=(e,...t)=>({strTag:!0,strings:e,values:t}),ae=e=>typeof e!=`string`&&`strTag`in e,C=(e,t,n)=>{let r=e[0];for(let i=1;i<e.length;i++)r+=t[n?n[i-1]:i-1],r+=e[i];return r},oe=(e=>ae(e)?C(e.strings,e.values):e),w=oe,se=!1;function T(e){if(se)throw Error(`lit-localize can only be configured once`);w=e,se=!0}var E=class{constructor(e){this.__litLocalizeEventHandler=e=>{e.detail.status===`ready`&&this.host.requestUpdate()},this.host=e}hostConnected(){window.addEventListener(ie,this.__litLocalizeEventHandler)}hostDisconnected(){window.removeEventListener(ie,this.__litLocalizeEventHandler)}},ce=e=>e.addController(new E(e)),D=()=>(e,t)=>(e.addInitializer(ce),e),le=class{constructor(){this.settled=!1,this.promise=new Promise((e,t)=>{this._resolve=e,this._reject=t})}resolve(e){this.settled=!0,this._resolve(e)}reject(e){this.settled=!0,this._reject(e)}},O=[];for(let e=0;e<256;e++)O[e]=(e>>4&15).toString(16)+(e&15).toString(16);function ue(e){let t=0,n=8997,r=0,i=33826,a=0,o=40164,s=0,c=52210;for(let l=0;l<e.length;l++)n^=e.charCodeAt(l),t=n*435,r=i*435,a=o*435,s=c*435,a+=n<<8,s+=i<<8,r+=t>>>16,n=t&65535,a+=r>>>16,i=r&65535,c=s+(a>>>16)&65535,o=a&65535;return O[c>>8]+O[c&255]+O[o>>8]+O[o&255]+O[i>>8]+O[i&255]+O[n>>8]+O[n&255]}var de=`h`,fe=`s`;function pe(e,t){return(t?de:fe)+ue(typeof e==`string`?e:e.join(``))}var me=new WeakMap,he=new Map;function ge(e,t,n){if(e){let r=e[n?.id??_e(t)];if(r){if(typeof r==`string`)return r;if(`strTag`in r)return C(r.strings,t.values,r.values);{let e=me.get(r);return e===void 0&&(e=r.values,me.set(r,e)),{...r,values:e.map(e=>t.values[e])}}}}return oe(t)}function _e(e){let t=typeof e==`string`?e:e.strings,n=he.get(t);return n===void 0&&(n=pe(t,typeof e!=`string`&&!(`strTag`in e)),he.set(t,n)),n}function ve(e){window.dispatchEvent(new CustomEvent(ie,{detail:e}))}var ye=``,be,xe,Se,Ce,we,Te=new le;Te.resolve();var Ee=0,De=e=>(T(((e,t)=>ge(we,e,t))),ye=xe=e.sourceLocale,Se=new Set(e.targetLocales),Se.add(e.sourceLocale),Ce=e.loadLocale,{getLocale:Oe,setLocale:ke}),Oe=()=>ye,ke=e=>{if(e===(be??ye))return Te.promise;if(!Se||!Ce)throw Error(`Internal error`);if(!Se.has(e))throw Error(`Invalid locale code`);Ee++;let t=Ee;return be=e,Te.settled&&(Te=new le),ve({status:`loading`,loadingLocale:e}),(e===xe?Promise.resolve({templates:void 0}):Ce(e)).then(n=>{Ee===t&&(ye=e,be=void 0,we=n.templates,ve({status:`ready`,readyLocale:e}),Te.resolve())},n=>{Ee===t&&(ve({status:`error`,errorLocale:e,errorMessage:n.toString()}),Te.reject(n))}),Te.promise},Ae=`en`,je=[`ja`],Me=[`en`,`ja`],Ne=globalThis,Pe=Ne.ShadowRoot&&(Ne.ShadyCSS===void 0||Ne.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,Fe=Symbol(),Ie=new WeakMap,Le=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==Fe)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(Pe&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=Ie.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&Ie.set(t,e))}return e}toString(){return this.cssText}},Re=e=>new Le(typeof e==`string`?e:e+``,void 0,Fe),k=(e,...t)=>new Le(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,Fe),ze=(e,t)=>{if(Pe)e.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let n of t){let t=document.createElement(`style`),r=Ne.litNonce;r!==void 0&&t.setAttribute(`nonce`,r),t.textContent=n.cssText,e.appendChild(t)}},Be=Pe?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return Re(t)})(e):e,{is:Ve,defineProperty:He,getOwnPropertyDescriptor:Ue,getOwnPropertyNames:We,getOwnPropertySymbols:Ge,getPrototypeOf:Ke}=Object,qe=globalThis,Je=qe.trustedTypes,Ye=Je?Je.emptyScript:``,Xe=qe.reactiveElementPolyfillSupport,Ze=(e,t)=>e,Qe={toAttribute(e,t){switch(t){case Boolean:e=e?Ye:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},$e=(e,t)=>!Ve(e,t),et={attribute:!0,type:String,converter:Qe,reflect:!1,useDefault:!1,hasChanged:$e};Symbol.metadata??=Symbol(`metadata`),qe.litPropertyMetadata??=new WeakMap;var tt=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=et){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&He(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=Ue(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??et}static _$Ei(){if(this.hasOwnProperty(Ze(`elementProperties`)))return;let e=Ke(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(Ze(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(Ze(`properties`))){let e=this.properties,t=[...We(e),...Ge(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(Be(e))}else e!==void 0&&t.push(Be(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ze(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?Qe:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?Qe:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??$e)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};tt.elementStyles=[],tt.shadowRootOptions={mode:`open`},tt[Ze(`elementProperties`)]=new Map,tt[Ze(`finalized`)]=new Map,Xe?.({ReactiveElement:tt}),(qe.reactiveElementVersions??=[]).push(`2.1.2`);var nt=globalThis,rt=e=>e,it=nt.trustedTypes,at=it?it.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,ot=`$lit$`,st=`lit$${Math.random().toFixed(9).slice(2)}$`,ct=`?`+st,lt=`<${ct}>`,ut=document,dt=()=>ut.createComment(``),ft=e=>e===null||typeof e!=`object`&&typeof e!=`function`,pt=Array.isArray,mt=e=>pt(e)||typeof e?.[Symbol.iterator]==`function`,ht=`[ 	
\f\r]`,gt=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,_t=/-->/g,vt=/>/g,yt=RegExp(`>|${ht}(?:([^\\s"'>=/]+)(${ht}*=${ht}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),bt=/'/g,xt=/"/g,St=/^(?:script|style|textarea|title)$/i,Ct=e=>(t,...n)=>({_$litType$:e,strings:t,values:n}),A=Ct(1),wt=Ct(2),Tt=Symbol.for(`lit-noChange`),j=Symbol.for(`lit-nothing`),Et=new WeakMap,Dt=ut.createTreeWalker(ut,129);function Ot(e,t){if(!pt(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return at===void 0?t:at.createHTML(t)}var kt=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=gt;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===gt?c[1]===`!--`?o=_t:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=yt):(St.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=yt):o=vt:o===yt?c[0]===`>`?(o=i??gt,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?yt:c[3]===`"`?xt:bt):o===xt||o===bt?o=yt:o===_t||o===vt?o=gt:(o=yt,i=void 0);let d=o===yt&&e[t+1].startsWith(`/>`)?` `:``;a+=o===gt?n+lt:l>=0?(r.push(s),n.slice(0,l)+ot+n.slice(l)+st+d):n+st+(l===-2?t:d)}return[Ot(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},At=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=kt(t,n);if(this.el=e.createElement(l,r),Dt.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=Dt.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(ot)){let t=u[o++],n=i.getAttribute(e).split(st),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?Ft:r[1]===`?`?It:r[1]===`@`?Lt:Pt}),i.removeAttribute(e)}else e.startsWith(st)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(St.test(i.tagName)){let e=i.textContent.split(st),t=e.length-1;if(t>0){i.textContent=it?it.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],dt()),Dt.nextNode(),c.push({type:2,index:++a});i.append(e[t],dt())}}}else if(i.nodeType===8){if(i.data===ct)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(st,e+1))!==-1;)c.push({type:7,index:a}),e+=st.length-1}}a++}}static createElement(e,t){let n=ut.createElement(`template`);return n.innerHTML=e,n}};function jt(e,t,n=e,r){if(t===Tt)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=ft(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=jt(e,i._$AS(e,t.values),i,r)),t}var Mt=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??ut).importNode(t,!0);Dt.currentNode=r;let i=Dt.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new Nt(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new Rt(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=Dt.nextNode(),a++)}return Dt.currentNode=ut,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},Nt=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=j,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=jt(this,e,t),ft(e)?e===j||e==null||e===``?(this._$AH!==j&&this._$AR(),this._$AH=j):e!==this._$AH&&e!==Tt&&this._(e):e._$litType$===void 0?e.nodeType===void 0?mt(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==j&&ft(this._$AH)?this._$AA.nextSibling.data=e:this.T(ut.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=At.createElement(Ot(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new Mt(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=Et.get(e.strings);return t===void 0&&Et.set(e.strings,t=new At(e)),t}k(t){pt(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(dt()),this.O(dt()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=rt(e).nextSibling;rt(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},Pt=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=j,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=j}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=jt(this,e,t,0),a=!ft(e)||e!==this._$AH&&e!==Tt,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=jt(this,r[n+o],t,o),s===Tt&&(s=this._$AH[o]),a||=!ft(s)||s!==this._$AH[o],s===j?e=j:e!==j&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===j?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},Ft=class extends Pt{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===j?void 0:e}},It=class extends Pt{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==j)}},Lt=class extends Pt{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=jt(this,e,t,0)??j)===Tt)return;let n=this._$AH,r=e===j&&n!==j||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==j&&(n===j||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Rt=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){jt(this,e)}},zt={M:ot,P:st,A:ct,C:1,L:kt,R:Mt,D:mt,V:jt,I:Nt,H:Pt,N:It,U:Lt,B:Ft,F:Rt},Bt=nt.litHtmlPolyfillSupport;Bt?.(At,Nt),(nt.litHtmlVersions??=[]).push(`3.3.3`);var Vt=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new Nt(t.insertBefore(dt(),e),e,void 0,n??{})}return i._$AI(e),i},Ht=globalThis,M=class extends tt{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Vt(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return Tt}};M._$litElement$=!0,M.finalized=!0,Ht.litElementHydrateSupport?.({LitElement:M});var Ut=Ht.litElementPolyfillSupport;Ut?.({LitElement:M}),(Ht.litElementVersions??=[]).push(`4.2.2`);var Wt=t({templates:()=>Gt}),Gt={h612ee972e5585763:A`JSON オブジェクト（スキーマ ${0}）`,had57861b5eb1998e:A`ファイルなし | Python コードで定義（<code>TaskAdapter</code>）`,hf139a496c0f9b763:A`${0} の出力から`,"no-runs-yet":`実行はまだありません`,s02044ab83f193b3b:`レート制限、エラー、タイムアウトなどで失敗した後の、次のモデルへの切り替え（Router のホップ）`,s02f7b7c4ece3e097:`実行されず`,s030b3188c7fcf26d:S`カスタムビュー ${0} はありません`,s0379fc73608ab971:`完了`,s0382d73823585617:S`${0}: ${1}`,s038b2a0deba58916:`ページ`,s03b454fb08e876ad:`タブ`,s03ee3cfb0919c62c:`タスク`,s03fb84d070eb4d43:S`古い試行 ${0} 件は非表示`,s04170ed88fb48665:`書き込まれていません`,s051e95917479e3a4:`実行中のエージェントのセッション`,s061a40d8b1403d96:`OutputContract`,s0622a6e6cb77254b:`トランスクリプト`,s0668067982f84dcb:`ユニットごとのステージとステップ（CursorStore）`,s066d70cf9d5e2915:`出力`,s06a59d9f860b0c38:`Esc: 1 つ上の階層`,s06ac9901d5ec124e:`依存先`,s06bab80ab006c3bc:`エージェントのセッション開始時に報告された値です。アカウント全体の値で、同時に実行中のタスクすべてに共通です。`,s07760df6abc2f6a0:`テキストフィルター（/）`,s0799e2b0ce300ca7:S`キャッシュ ${0}`,s07e46807b4a9183c:S`+${0}`,s087d6f07b52b30ec:S`${0}%`,s08b35907b5589afa:`いいえ`,s09323b2ac0a8afed:`出力の検証: OK`,s09bb59cd137c1af4:`プロンプトなし`,s0ad3c18e14f52ceb:S`出力ファイル ${0} 件が OK`,s0b237aba4a56eb22:`エージェントのセッション開始時のサブスクリプション利用率（アカウント全体）`,s0b355fde970b0df9:`OK`,s0cf77430f4bd7c5c:S`モデル切り替えのあったタスク ${0} 件`,s0d7aa7237dcb1b28:S`キャッシュ書き込み ${0}`,s0dbd76eb398aa733:`未実行（入力ファイルの不足または検証エラー）`,s0e6bbd9fe1101fbd:`問題`,s0ea064cda0585ae9:`プラグインディレクトリ`,s0f04e0aca045fbe9:`一部省略`,s0f136ff2c086b760:`リセット済み`,s10337c73438593bc:`再開カーソル`,s1072ae09dfd51f53:`種別の最初のタスクの開始時に記録（definitions/&lt;kind&gt;.json）`,s10bcccd513757153:`まだ書き込まれていません`,s1147e23008e266b7:S`${0} 型の JSON 値`,s115763f2236ae9b6:`過去 24 時間`,s1198336b172c6e1a:`モデル切り替えのあったタスク 1 件`,s123b7254b44dd148:`待機中`,s125a86b2f45bbb25:S`要素 ${0} 個`,s12c35dcdc5890192:`型の不一致`,s14bd607323778cb3:`コーディングエージェントが報告した値`,s150f53f8651b4384:`出力`,s156d30b96fb26c7f:`なし（任意）`,s158eba9bc2227ce3:S`週の利用率 ${0}`,s1633e83dc53b5d08:`検証対象のファイルなし`,s168ae294e3e72ce4:`検証のタイミング`,s1703f5cfa8ed0cc9:S`実行されず ${0} 件`,s179ba9809bdf35c7:`アカウントごと、最初の値 → 最後の値`,s17ee023c53dcd83c:`書き込み待ち（タスクが待機中）`,s18d4d02c2e47cf0f:S`ループ内の ${0}`,s19ed92a422ad7e4c:`上限: max_concurrent`,s1a20210c3f1e40c9:S`スキップ ${0} 件`,s1a3bf4da26280428:`種別 · ユニット`,s1acc85c236fed879:`書き込まれていない出力 1 件（タスクが未実行）`,s1b5c88ed6d70d50e:S`タスクは ${0} 回目で完了`,s1bb7c4234aa7d213:`すべてのタスクが開始済み`,s1bf54dcd1c885a20:`実行中のプロセスなし`,s1c0f7e3a9a6bce79:`パラメータ`,s1c2af4de03b03b48:`タスクが選択されていません`,s1c4244f27dc0a0ad:S`セッション開始時の利用率（アカウント全体）: ${0}`,s1c76dcdfd0d3326d:`実行に登録されたすべてのタスク（種別ごと、plan.jsonl）`,s1cc744978f1e1e36:`実行中の Python タスク`,s1db2936d905dfc71:`API エラー`,s1dc338639fe7aae9:S`試行 ${0} 回`,s1dd7ab260efc97bf:`実行中のタスクなし`,s1e9a9d076c64051d:S`プロンプト（${0} 文字、ほか ${1} 文字は未保存）`,s1ebbae8f5810b65b:`入力`,s1f53dce0721a5fdc:S`所要時間 ${0}`,s2073c04640f9ffe1:`修正依頼: 検証エラー後の、同じエージェントのセッション`,s20e04bdc808a6442:S`リセットまで ${0}`,s217ae8afd4252eff:`あり`,s2216c1ec1d2b68a8:`JSON ではありません`,s224181db56bd4f90:`ツール実行中に中止`,s229e98b8f3010c9f:S`修正依頼 ${0} 回で完了。最初の検証エラー: ${1}`,s22d4df747c023383:S`修正依頼 1 回で完了。最初の検証エラー: ${0}`,s23005b43f30a04ed:`スキーマにないフィールド`,s234af65b52814aa0:`終了した試行はまだありません`,s236ae937cbcd6a39:`拡大`,s23ba00b0f333e17e:S`${0} 回の試行がすべて失敗: ${1}`,s23f40d3ffdd352a6:`定義はまだありません`,s2575361362fcf642:`OutputContract・InputContract を宣言したタスクはありません`,s26012de2ae38a284:`API 呼び出し 1 回`,s26bae2d058ab07f8:`ユニットなし`,s26bb7d0992115fe1:`実行した試行の回数（リトライを含む、journal.jsonl）`,s26e1e2905dce8250:S`API 呼び出し ${0} 回`,s27bbde3f68fad181:S`ユニット: ${0}`,s28f91da403800c05:`InputContract`,s2a2e8a5afcc8d89a:`現在`,s2ac18b95949a85cb:S`${0}: ${1}、次のモデルに切り替え`,s2b82c03a0f482d56:`入力ファイルの不足または検証エラー`,s2cf203a7f1d1b7cb:`修正依頼: 出力が検証エラーになった後の、同じエージェントのセッションでの次のラウンド`,s2dd7dfcce562730a:`試行の結果（stop）`,s2e3f7c747d87ba60:S`ほかの出力 ${0} 件`,s2ec303c39937657c:`タスクは実行中`,s2f3435308f48080e:S`${0} 周`,s2f3c9db4daa3e192:`問題なし`,s2f4e0fd086ad4b96:`すべての出力`,s2f54740b39931f87:`定義なし`,s2faec8a0d7db08dd:S`5 時間枠の利用率 ${0}（リセット ${1}）`,s2fe3f0ef38a252c7:`ツール`,s321b04e2b2f863d5:`余分なフィールド`,s326385425f7ff3c5:S`キャッシュ読み込み ${0}`,s33b572e03cbb49a2:`パイプラインの階層`,s343dead26eec35c9:`新しいイベント 1 件を表示`,s3445d9f4d9c68070:`グラフで表示`,s34970ae2312009f5:`エラーの内容は修正依頼のプロンプトに記載`,s351d1cb40ce52b1e:`終了した試行なし`,s352069454f38346a:`ファイル全体`,s355f4ca5b99c3871:`入力ファイルに検証エラー`,s367d079d1aed1358:`料金`,s36eb49cc97df66bc:S`所要時間 ${0}`,s3700ce266079b566:`Web 検索 1 回`,s370bd0b51ee4fda0:S`報告時刻 ${0}`,s37da018e1fe6a0d7:`スキーマ以外の検証（validators）`,s387a4a41718122cb:S`検索結果 ${0} 件`,s3904df152788b23c:`JSON オブジェクトではありません`,s39ee2f1fc48e6bc3:`パイプライン`,s3aa67b8233b5ecd0:`出力ファイルなし`,s3afd657caafb54ce:`上段は入力 / 出力トークン、下段はキャッシュ読み込み / キャッシュ書き込み`,s3b32dd23d086c992:`プロセスツリー`,s3bde79a5267baa21:S`task_detail コールバックが失敗: ${0}`,s3c0d17bad169557b:`なし`,s3c6c1ae328e812d5:`実行した試行の回数`,s3cd8af104999d502:`実行中のエージェントのセッション 1 件`,s3d03990e188bfbff:`エージェントのセッション`,s3d197283cb019b5a:`概要`,s3d99e317c3b7b422:`検証エラー後の、同じエージェントのセッション`,s3d9b2f1277134dfc:`テキストファイル`,s3f18b1a78ce1a960:`各タスクが書き込むファイル`,s3f6e4868742b58de:S`${0} 回目で完了（失敗 ${1} 回）。最初の失敗: ${2}`,s3f7074a6bbbd7726:`修正依頼`,s3fd6bd99e3f6a5be:`開始`,s40750d44c5ea3271:S`${0}: 入力`,s4085b471de2e2215:`週の利用率`,s40a3fbe1df331f66:`依存先タスクからの入力`,s4134711b0b981089:`Tab: 次のノード`,s4156c144093d2565:`修正依頼が 1 回以上あった試行`,s423b98420bc4f51a:S`${0} 回目で完了（失敗 1 回）。最初の失敗: ${1}`,s42a1ebe17efda727:`フィールド`,s42c16f17debe21c7:S`${0} ステップ完了`,s42cbd8dca939a9c7:`検証`,s43809cc80b3f099a:`ハイライトを解除`,s43ab3e3c4dea42fc:`入力ファイル`,s448ad430047b3ff5:`ファイルの検証: OK`,s451bb7dd42aaf221:`料金の高いタスク`,s45de7528c20a0792:S`${0}（カスタムビュー）`,s467ceab5071e77a3:S`1 周: ${0}`,s46f1d86ffec6223c:`エラーで終了`,s473bad4c26a1a663:`キャッシュ読み込み`,s475eae6093ad432f:S`${0} 回目 | モデル切り替え`,s478b912874fef59f:`検証対象のファイル（OutputContract、InputContract）`,s47b9912260b01c3c:`Python タスク`,s47c42ef44972974f:`未対応のイベント`,s48287bbcb6ba7b8d:S`終了 ${0}`,s48e186fb300e5464:`所要時間`,s49098dfd8a30a9b7:`モニターのサーバーに接続済み`,s491765412b82838e:S`${0} のループ`,s4abcddbf0c24a4e2:S`${0} 日前`,s4d613d768e2faa0d:`検索結果 1 件`,s4d890c06c9c42dee:`モデル切り替え`,s4dc1b9906b081f0b:`出力ファイル 1 件がありません`,s4efee5b48a4593cb:`ループ`,s4f0af1e75e3f4e0d:`スキーマにない`,s500fd71a4232050e:`空`,s521a16a18cfbcf5a:`1 ユニット`,s52cfd5bdf53cbac3:`カスタムビュー`,s53c57cf5a0992de1:S`${0}: 未実行`,s53ebfdf5583cbe71:`次の周`,s54393bfa280ea55b:`プロンプト`,s552240946fb80e49:S`フロー呼び出し ${0}`,s5552cf25dfb16715:`プラグインディレクトリ`,s558d71789938dd8d:`認証情報の不一致`,s55ed13a29f9e56db:`タスクの開始時に検証`,s55fa598b754cc3cc:S`${0}（${1}）`,s5667ab3a2fddedf6:S`（ほか ${0} 文字は未保存）`,s56838581fa8422a5:S`後続タスク: ${0}`,s571b714236b36ed9:S`入力 ${0} がありません（${1} が未実行）`,s57402fcb8174003c:S`キャッシュ書き込み ${0}`,s585632ad63b34266:S`入力 ${0} がありません（${1} が失敗）`,s58c754018ec47b5f:`実行履歴`,s594159521842aa08:S`修正依頼 ${0} 回`,s59e4f00624df1f3f:`上限に接近`,s59f1f6a6e10801e3:`出力ファイル 1 件が OK`,s5ab755785f15d57e:`並び順`,s5b2aca393ddc3642:`修正依頼のあったタスク 1 件`,s5b91c14a6a040e1e:`種別ごとのトークンと料金`,s5cd51fca94ab558d:S`エージェントのセッション ${0} 回`,s5e30a7b87ccdc74f:`書き込みなし（タスクが未実行）`,s5e6c4b6767bd9690:`テキスト（JSON 文字列）`,s5f22ded7520dee36:`ロールなし`,s5f31efe25292c85d:`エージェント・モデル・認証情報`,s5f43af3669b1e098:`ソース`,s5f7e595afb1d20c1:`なし（必須）`,s5ff154de087b8fbf:`エージェントタスク`,s60147fb4fa4a8e0c:`実行中`,s605757aea05668c5:S`未実行の後続タスク ${0} 件`,s62035be5de828c62:`キャッシュ書き込み`,s629576c6b305d539:`任意`,s630a7291de06d7e3:`実行履歴の未実行のタスク`,s6338c9c6cf8d4720:`入力・出力トークン（全試行）`,s649816288746372b:`後続タスク`,s65ca38fd016064d1:`中断`,s6645c79330d551d1:`拡大（Ctrl + スクロール）`,s6647f4305129ff48:`ファイルなし`,s664bf0dfe5ccdd70:`ツール呼び出しが戻る前に実行が終了`,s670ef751f29dc9ae:S`${0} ユニット`,s680fc90489553ed6:`タイムライン`,s68818ff23f9c3cd6:`その他の検証`,s69522c8fd29e217c:`修正依頼 1 回`,s69990579b19fd554:S`スキーマ ${0}`,s6a8fac496ab75484:S`入力 ${0} がありません（${1} が未完了）`,s6aabc9569e449784:`未実行（入力ファイルなし）`,s6b8a04c7fc4c0cfd:S`同時実行 ${0}/${1}`,s6b94519d3d694140:`タスクなし`,s6c306ba2a3eafe04:`依存先タスクなし`,s6c80deca380c99b3:`タスクなし`,s6c86e2a18e78587f:S`依存先タスク ${0} が失敗`,s6d36170fcecb00d0:`依存先タスク`,s6d739294ba8eba32:S`${1} タスク中 ${0} 件完了`,s6dbe9cb1faacdff3:S`${0} 文字`,s6ebc9bd6feae62a3:`読み込み中…`,s6f145ecab7e01aae:`API 呼び出し`,s6f6ef83186f41f9c:`すべてのエージェントのセッションの合計（同時実行の分も含む）`,s6fa4fa0db6637ca7:`フロー呼び出しがエラーで終了`,s706837052444dc71:`実行グループ`,s7081cf6429d6e736:S`ループ ${0} 周目`,s70a75a654c87e121:S`タスク終了後の利用率: ${0}`,s70af97de3ad8fb23:`種別`,s71900089efd0b3f6:S`モデル切り替え: ${0}`,s7233e6b5b69a2313:`古い試行 1 件は非表示`,s7239ff29fb5724bc:S`修正依頼のあったタスク ${0} 件`,s72dc3c241ce33d1c:`ユニットごとの周回数`,s72dd85d5a32d1dc3:`キャッシュ読み込み`,s737a2225351a2d83:`ループの周回数`,s73d2ca96ea1a1a1f:`未実行の後続タスク 1 件`,s755ec54babc00670:S`プラグイン ${0}`,s75834d577f713a10:`エージェントのセッションなし`,s75ee52426b34dd6d:`実行を検索`,s7671567ef7075153:S`${0} モニター`,s769a35c122b0add4:S`${0}: ${1}、${2} に切り替え`,s77ec32fb8248c021:S`未実行 ${0} 件`,s78fd8c03f8c967f3:`トークン`,s79a4abd140c07a19:S`未対応のイベント: ${0}`,s79faeb77f29174c8:S`5 時間枠の利用率 ${0}`,s7a14301773287a5c:`エラーで終了したフロー呼び出し 1 件`,s7a30a0774744040b:`出力ファイル`,s7a4c9d94aaf75c45:`権限エラー`,s7ae3a2df31f642c2:`試行が 2 回以上のタスク`,s7ae683e966f797d8:`タスクは待機中`,s7b16665b242b03f9:`入力ファイルなし`,s7b1cef9707986270:`修正依頼のあった試行`,s7c08c2107990421e:S`${0} を表示`,s7c95876637f6a9d7:`フィルター`,s7ccddac9af610a9c:S`${0} 回目で完了（失敗 1 回）`,s7cfd548e0b7e3ad7:`出力が止まった`,s7e796fe83982863f:S`ロール ${0}`,s7ff1975047cd672c:`コーディングエージェントが使ったモデル`,s803ce7e1a2294d50:`ファイル`,s8162d2730a5efc31:`モデル切り替えなし`,s81784b8f13a711a6:`モデル切り替え: 次のモデルでの新しいエージェントのセッション`,s81816ae715e0080c:`入力ファイルの不足または検証エラーで、タスクは未実行`,s822f38a61c9dbabc:S`以前の試行のモデル: ${0}`,s837f3597be0e0bda:S`書き込み ${0}`,s83a117a0e5a969a7:`1 ステップ完了`,s84126fa92f00b4ef:`たった今`,s843c1705315bbf4e:S`修正依頼 ${0} 回後`,s84fb675fb17d4455:`リトライ`,s851d0f73d02cf0b5:`ファイルの値`,s85994a70cd39166c:`実行中`,s85e6ce57abc3c81c:S`${0}: モデル切り替え`,s863c685c886dd083:S`入力 ${0} がありません`,s864c948d4629240f:`全体を表示`,s877a8bf58317ec9e:S`${0} 回目の失敗後の、新しいエージェントのセッション`,s87aaf1391fb727b7:`実行されず`,s87b0c0d87ec9c3a1:S`モデル切り替え後に完了: ${0}`,s87cfcf0fecad5ace:`修正依頼 1 回後`,s888d98a196a240d8:`入力`,s88e6f151026426e7:S`修正依頼 ${0}`,s892f20ba2aadea33:S`入力 ${0}（${1} の出力）がありません`,s89ece7813063852e:`パラメータなし`,s8a56a8c8bd19c9c7:`なし`,s8a59bcc106a68c08:S`PID ${0}`,s8ab194afc8c3ff86:`コーディングエージェント`,s8ad90bcc234667ee:`周回数`,s8b14867a2824dc66:`リトライしたタスク`,s8bbe7f1c618318b1:`終了したすべての試行から集計（journal.jsonl）`,s8c1837e74a81ad0d:S`${0} 分前`,s8d4bb019f3bc7202:`PID`,s8dd1924ee42c1f45:S`キャッシュ読み込み ${0}`,s8dfeaf9950df0ffa:`オブジェクト`,s8e337d18c39babc7:`アシスタント`,s8e609688324130a6:`Python コードで定義`,s8e92b07ba776ed4a:S`ほか ${0} アカウント`,s8eec5711640b68b9:S`コーディングエージェントのイベント種別のうち、このバージョンの contraagent が対応していないもの: ${0}`,s8f26e0f086cc2787:`ユニット`,s8f5f41272268128f:`未実行`,s8ffca4adce22d531:`このタスクの入力としても宣言`,s90f3ce6dfe4ed0ce:`認証エラー`,s9147091d090a92d4:S`最大 ${0} 周`,s919d209719302bd3:S`${0}d ${1}h`,s9246c889a0392130:S`モデル ${0}`,s92a32f8361a3a3b0:S`依存先タスク ${0} 件の出力待ち`,s92b7e489ad4779c7:S`5 時間枠 ${0}`,s9340e2a9e1808cbd:`試行 1 回`,s947887a004e02e33:S`作成元: ${0}`,s94d63573d312fe9b:`認証情報`,s94d8c911acbe572f:S`出力ファイル ${0} 件に検証エラー`,s94f08f46277af7d6:`実行中のタスク`,s95f6abd3bc028e9c:S`依存先: ${0}`,s967a2db7049dc90e:S`失敗 ${0} 件`,s96ad55844e8c85d9:`コンテキストの上限`,s96cd46414e7cb3ee:S`出力 ${0}`,s9709015aaaed72e8:`実行中ではありません`,s97c3c9984ad4bbbc:S`修正依頼 ${0} 回で完了`,s980dd0446ac478b4:`テキストフィルター`,s98fc8cf0000154d3:`入力ファイルなし`,s9a23fee499e1a22d:`すべてのプロセス`,s9a44f95f7acf28e0:S`失敗: ${0}`,s9a629cca97d7a771:S`Web 検索 ${0} 回`,s9b1a610c6b10af9d:`実行中ではありません`,s9b7d6466c580aa00:`書き込みなし（タスクが失敗）`,s9d60d7651126c205:`最終応答なしで終了`,s9de543933e6e703a:`モデル`,s9e06cbf9c5f57859:S`状態: ${0}`,s9e8afbe69b10d822:`未実行（入力ファイルに検証エラー）`,s9f0023dbc7b35c31:S`入力 ${0}`,s9f7452dd75d54d31:`エラー`,s9f979c9a653c5aa5:`料金の上限`,s9fbbc819fe7e66aa:`実行`,s9fd13600c5948a5d:`タスクの開始前からあるファイルも有効`,s9ff6bfdb36b47dd6:`モデル切り替え`,sa0a6e71350fd953b:`出力を待つ`,sa12ff035c78855af:`コーディングエージェントが認証に使ったアカウントまたは API キー（credential）`,sa23567d1be73e6a7:`ターン数の上限`,sa335a9687e946152:`後続タスクなし`,sa358ec1ff0c833b9:`ロール`,sa35c067275510aa7:`試行`,sa390213ff60c0fd9:S`実行中のエージェントのセッションの新しいイベント ${0} 件を表示`,sa3c9339de23c1752:`形式`,sa3d3f3845c4fa2c4:S`週の利用率 ${0}（リセット ${1}）`,sa434ad4d2100f245:`作成元`,sa48318e1513f445c:`コマンドライン`,sa50a6326530d8a0d:`折りたたむ`,sa58fd816ed43f98e:`周回数`,sa6295f265bf36f55:S`${0}: トランスクリプト`,sa65ede9447b8f6f0:S`${0} 回目で完了（失敗 ${1} 回）`,sa66db52d0401c35d:S`前の ${0} 行を表示`,sa71f10bfe8f2e3b9:`期待する型`,sa74be5e915086e8e:`縮小（Ctrl + スクロール）`,sa7678024227276be:`その他の入力ファイル`,sa84bd87e8f0df3f5:S`新しいイベント ${0} 件を表示`,sa86ea054ad5277ce:S`${0} 時間前`,sa87126e2d984d351:`ソースを表示`,sa8865b3bf47ba11f:S`${0} の入れ子のループ`,sa8bd7200899b14c8:`Shift + 矢印キー: 依存先タスク・後続タスク`,sa9ba2bef6a85be35:`タスク詳細`,saa08e9b351f629c4:`書き込み待ち（タスクが実行中）`,saa29a2ac03cd9d19:`理由`,saaaf4d8d7823ecc2:`5 時間枠の利用率`,sab5bbfc5ec1101a1:S`${0} 行目`,sabd480ab5c691fa7:`思考`,sac1ead3bc64c3402:`モニターのサーバーに未接続`,sad3e3c8146fc920f:`状態`,sad951affb16c18e8:`API リクエストを再送`,sae5d87e99fe081e0:`必須`,sae675aed0baadfc5:`実行履歴のリトライしたタスク`,safdeae829048fe4f:S`${0} 回目が失敗: ${1}`,sb05ee36313adad06:`エラー`,sb067d7b999cdf867:`実行履歴の修正依頼のあった試行`,sb0c5ebf2450daf53:`サブスクリプションの利用率`,sb0fd4b074f0dc196:`Python タスク 1 回`,sb105a27af3c34dd9:S`未実行: ${0}`,sb1068f146c4596c3:`検索語`,sb1ffef0fea624d13:`前の 1 行を表示`,sb26a93fd31e2f700:`登録順`,sb26f6e41558f71ed:`表示中の階層の外`,sb271968591691cd3:`Enter: 開く`,sb289ca473d87fa82:`キャッシュ書き込み`,sb31160f9d54a1178:S`プロンプト（${0} 文字）`,sb45a9b8907f0b38a:`リトライしたタスク 1 件`,sb4d67c0a20dacf94:`トランスクリプトなし`,sb51d4fbebeb0e2ec:`パイプラインのプロセス内`,sb53f7a197981b790:`はい`,sb557a3a544242a40:`コーディングエージェントが報告した値`,sb5ae7a6b849639af:`未実行`,sb6bb16aa7550533d:`タスク実行中の書き込みが必須`,sb89b16909f010061:`エージェントのセッション 1 回`,sb9855c13b2b8461f:S`${0}: 完了`,sb998a18b54658de7:`トークンと料金`,sb9c8c7e97598bc93:S`Python タスク: ${0}`,sb9e681f6b83c4bc2:S`${0} 回目 | 修正依頼 ${1}`,sba376ab929e3896d:`1 周`,sba781480d2e52d6a:`ほかの出力 1 件`,sba8659178319945b:`検証を通るファイルを書き込む前に、タスクが失敗`,sbaf87689cccc53eb:`要素 1 個`,sbb202211084591ed:`開始時の利用率`,sbb77dd1d4c08e701:S`${1} タスク中 ${0} 件が未完了`,sbb99d4ec27fbb263:`終了`,sbc65d1b9648966de:S`${0} 周: ${1}`,sbc95529382a8202f:S`以前の試行のモデル: ${0}`,sbca0391cb2c7c054:`タスクの開始時`,sbcce076a4882d945:`依存先タスクが失敗`,sbce72abc083f229d:`失敗した試行の後の試行（毎回新しいエージェントのセッション、RetryingRunner）`,sbd4aeb401e751129:`実行を切り替え（r）`,sbe299a9270c76655:`実行履歴の失敗した試行`,sbed050affb1455dd:`全試行の合計`,sbf189e73c517d820:`種別のロール`,sbf299a5316967a33:`アクティビティなし`,sbf9c5c5a8e5efad4:`失敗`,sc032b109be3096a1:`それ以前`,sc15ad44c7902a717:`スキップ`,sc1ae48fd5a58a916:S`待機中 ${0} 件`,sc1b187568fa11c8c:S`リトライしたタスク ${0} 件`,sc46bcff777c978a4:`タイムアウト`,sc5751344f7cedf0f:S`入力 ${0} に検証エラー`,sc5b9f26a8c698f76:`次のモデルでの新しいエージェントのセッション`,sc61813a1424783fc:S`週 ${0}`,sc65ea2cf2f21a13a:`縮小`,sc6c0d07e39170334:S`書き込まれていない出力 ${0} 件（タスクが未実行）`,sc6fd207e5b80c46e:S`エラーで終了したフロー呼び出し ${0} 件`,sc797fd9076cc136d:`タスク`,sc7d1e9a9024b4f9c:`同時実行（上限）`,sc87df95c02f9306d:S`終了 ${0}`,sc92905d14a9421f3:`空き`,sca4ca1724004c913:`プロセスなし`,sca68313fa6851125:`プレビューを表示`,sca7fed2bef53cb99:`ロール`,scb862deeee160b4a:`終了（未完了のタスク 1 件）`,scb967cb2ce8bd344:`最終試行の終了時刻`,scbd3558d2cfc7dc3:`全文`,sccad21b77f9a317c:S`最も高い種別: ${0}`,sccce3de7b4abfdfe:`モデルが応答を拒否`,scd693bed9950dfb4:`ループの各周を表示`,scd945ec17b61f103:`エージェントの所要時間`,scd99caf8298e3611:`入力でもある`,scdece4ad70d57deb:`ループ`,sce26f796a9b94ef1:`各タスクが読み込むファイル（タスクの開始時に検証）`,scf1f6260b486064d:`一致する実行なし`,scf39b102c7cc194f:S`${0} を開く`,scf4185bf1a2d6adf:S`完了 ${0} 件`,scf70a5a7a06e1fa5:`レート制限`,sd1f67ae2a58049b0:`ファイルの検証に使うスキーマ`,sd3c028fcc08b18ab:`登録済みのタスクなし`,sd3ec6686aaaf1324:S`終了（未完了のタスク ${0} 件）`,sd47e3a005069edb9:`ローカルの認証情報（ambient）`,sd489b7dc205394ef:S`出力ファイル ${0} 件がありません`,sd5a8fb496330927a:`ファイルに検証エラー`,sd5da7ee4a43a6b2d:S`トークン: 入力 ${0}、出力 ${1}、キャッシュ読み込み ${2}、キャッシュ書き込み ${3}`,sd654656b8bf1ee00:S`${0} のタスクを表示`,sd68011705bf4b72f:`プロンプトは保存されていません（keep_transcripts = false）`,sd7338946b42394f4:`失敗`,sd7445330352af2c5:`検証対象のファイル`,sd747248fb64d7bb2:`なし（任意）`,sd757815e3da2dde5:`検証エラー`,sd7768c230e48ac70:S`全体の ${0}%`,sd77d82bf43357ecd:`実行中のエージェントのセッションの新しいイベント 1 件を表示`,sd794d5178cc31502:`出力が検証エラーになった後の、同じエージェントのセッションでの追加のラウンド（rounds）`,sd798aaccd0308806:`結果を受けて作成`,sd7d77bef673bd45f:S`入力 ${0}（${1} の出力）に検証エラー`,sd8284849892c5c5a:`タスクの開始前からあるファイルは無効`,sd93128c9fde34bb6:S`依存先タスク ${0} の出力待ち`,sda249baca3c52d27:S`セッション開始時の利用率: ${0}`,sda800fa8314eb82c:S`すべて表示（${0} 文字）`,sdb1595f5c742dfbb:`入力`,sdb80a6330c0fa072:`出力に検証エラー`,sdc40078597054827:S`実行グループ ${0}`,sdc51fb6761fd6e91:`完了`,sdd0fb64c2928422f:`コーディングエージェントのイベント種別のうち、このバージョンの contraagent が対応していないもの`,sdd826d4b3e02f41b:`修正依頼なし`,sdf452c95fdeb4be0:`リトライなし`,sdf922ccc13491763:`リトライ後に完了`,se162d3485ea0d5d7:`出力ファイル 1 件に検証エラー`,se2788d18bd1f9873:`タスクを実行した CLI（claude、omp）`,se2bad0e4af9e9155:S`キー ${0} 個: ${1}`,se2cd8c3175e8f91f:S`期待する型: ${0}`,se3b4c857f91f80d7:`キーボードショートカット`,se5d1247fe34fbb95:`monitor.Panel`,se61f0dc09b51fd35:`パイプラインのプロセス内の関数`,se66872955dc59191:`1 タスク`,se7102b7d5942a59c:S`${0} 回目`,se90f184c6aa3ffbb:`認証情報`,sea4f20ea1ece70a0:`定義`,sea67cb607ba79bea:`矢印キー: マーク`,sea748bf5cf6f28f3:S`${0} タスク`,sea7bdd2b70c8c2bb:`実行の一覧`,seac9afef1a00b5e8:`待機中`,sebada5168620c5fe:`既定`,sec2574ea71a53cc7:`すべての種別`,sec749d36a5ebf2a6:`コーディングエージェントが使ったエージェント定義（agents/&lt;role&gt;.md）`,secc170560fffe506:`上限に到達`,sed0a4ed4fcf1c063:`タスクごとに 1 つ（Backend.run）`,sed7bd1552ea928f8:`種別または関数`,seda52979691efde8:`ファイルなし`,sede9056322866918:`ステージなし`,seea0f53b4dbb2fb3:`結果`,seee13c69133b70b7:`スキップ`,sef0ce050d92c35e2:S`実行中 ${0} 件`,sefcf950b3cc4fc3b:`言語`,sf05d9f2cb461bc10:`表で表示`,sf113fa256db9617b:`終了時刻`,sf14df172fd566bcc:`最初のエージェントのセッション`,sf2b0c091b94a0303:`トークンの報告なし`,sf2d62a5d815803af:S`関数 ${0}`,sf2e5c0d258c9b689:`定義`,sf39e43f2714690bc:`周回数`,sf3cb3cd43bbe95c2:`ほか 1 アカウント`,sf3e2e1c7b6313910:`カスタムビュー`,sf466a6f271f0b682:S`${0} 周目`,sf4897f85932ebf42:`終了後の利用率`,sf56cc81a8429fcb0:`試行の終了後に、同じアカウントで最初に報告された値`,sf5dbf772d898f6e7:`ユニットごとではなく、実行ごとに 1 回実行されるタスク`,sf6e66e6e9a5d83ff:`トランスクリプトは保存されていません（keep_transcripts = false）`,sf7b714930ed98b54:S`不明（${0}）`,sf89368b65754b7f6:S`フロー呼び出し ${0} 回`,sf93c7009f950942a:`合計`,sfa04f4ef1995407e:`テキスト`,sfa6a5b4597c720bc:`フィルターに一致するタスクなし`,sfadf0e9dfc4b3030:`修正依頼 1 回で完了`,sfb65f5d860c9a106:S`実行中のエージェントのセッション ${0} 件`,sfbb1f6b888aed522:`失敗した試行`,sfc7ed987d0fe9679:`再開カーソルなし`,sfd313341ca75a38d:S`リトライ後に完了 ${0} 件`,sfd5b8cae918b42cb:S`要素 ${0} 個: ${1}`,sfd77270c3f54f664:`出力`,sfdd447bcde2c13ba:`プロセス`,sfddde3643e5505f4:`試行: 新しいエージェントのセッション`,sfde497acd6a6a561:`ファイルにない必須フィールド`,sfe771bfc3355dd51:S`${0}: 入力と出力`,sfe9c9abcded61e50:S`プロセス ${0}`,sff660af26c203189:`登録済みのタスクはまだありません`,sff6ef2732281bb26:`すべての試行が成功`,sffa12312d4ff4b9c:`定義なし`,sffb00562b267f0a5:`エージェントの起動に失敗`,sfff7f6b9ec291984:S`Python タスク ${0} 回`},Kt={en:`English`,ja:`日本語`},qt=new Map([[`ja`,Wt]]),{getLocale:Jt,setLocale:Yt}=De({sourceLocale:Ae,targetLocales:je,loadLocale:e=>Promise.resolve(qt.get(e))}),Xt=`contraagent:locale`,Zt=e=>Me.includes(e);function Qt(){try{let e=globalThis.localStorage?.getItem(Xt);if(Zt(e))return e}catch{}for(let e of globalThis.navigator?.languages??[]){let t=e.toLowerCase().split(`-`)[0];if(Zt(t))return t}return Ae}async function $t(e){try{globalThis.localStorage?.setItem(Xt,e)}catch{}await Yt(e)}function N(e){if(e==null||Number.isNaN(e))return`—`;let t=Math.max(0,e);if(t<.05)return`<0.1s`;if(t<9.95)return`${t.toFixed(1)}s`;let n=Math.round(t);return n<60?`${n}s`:n<3600?`${Math.floor(n/60)}m ${String(n%60).padStart(2,`0`)}s`:`${Math.floor(n/3600)}h ${String(Math.floor(n%3600/60)).padStart(2,`0`)}m`}var en=new Map;function tn(e,t){let n=`${e}|${t}`,r=en.get(n);return r||(r=new Intl.DateTimeFormat(e,{...t?{month:`short`,day:`numeric`}:{},hour:`2-digit`,minute:`2-digit`,second:`2-digit`,hourCycle:`h23`}),en.set(n,r)),r}function P(e,t=!1,n=Jt()){if(!e)return``;let r=new Date(e);return Number.isNaN(r.getTime())?e:tn(n,t).format(r)}function nn(e,t=Date.now()){let n=Date.parse(e||``);if(Number.isNaN(n))return``;let r=Math.max(0,(t-n)/1e3);return w(r<60?`just now`:r<3600?S`${Math.floor(r/60)}m ago`:r<86400?S`${Math.floor(r/3600)}h ago`:S`${Math.floor(r/86400)}d ago`)}var rn=e=>e.charAt(0).toLocaleUpperCase(Jt())+e.slice(1),F=(...e)=>e.filter(Boolean).join(` | `),I=(e,t=` · `)=>`${e.kind??``}${e.unit?t+e.unit:``}`;function an(e){let t=(e||``).trim();if(!t)return``;let n=(t.split(`
`)[0]||``).trim();return n.length>100?`${n.slice(0,100)}…`:n}var L=e=>String(e??``).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`);function R(e){let t=e??0;return t<1e3?String(Math.round(t)):t<1e4?`${(t/1e3).toFixed(1).replace(/\.0$/,``)}k`:t<1e6?`${Math.round(t/1e3)}k`:`${(t/1e6).toFixed(1).replace(/\.0$/,``)}M`}function on(e){return e==null?`—`:e===0?`$0`:e<.001?`<$0.001`:e<1?`$${e.toFixed(3)}`:`$${e.toFixed(2)}`}function sn(e){let t=new Map;for(let n of e)for(let[e,r]of Object.entries(n.unread_events??{}))t.set(e,(t.get(e)??0)+r);return[...t].map(([e,t])=>`${e} ×${t}`).join(`, `)}var cn=new Set(`and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield`.split(` `)),ln=new Set([`None`,`True`,`False`,`self`,`cls`]),un=new Set(`str int float bool list dict set tuple bytes object type len range print isinstance super Optional Literal Any Union Path`.split(` `)),dn=new RegExp([`(#[^\\n]*)`,`((?:[rRbBfFuU]{0,2})(?:"""[\\s\\S]*?"""|'''[\\s\\S]*?'''))`,`((?:[rRbBfFuU]{0,2})(?:"(?:[^"\\\\\\n]|\\\\.)*"|'(?:[^'\\\\\\n]|\\\\.)*'))`,`(@[A-Za-z_][\\w.]*)`,`(\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)`,`([A-Za-z_]\\w*)`].join(`|`),`g`);function fn(e){let t=``,n=0,r=``;dn.lastIndex=0;for(let i=dn.exec(e);i;i=dn.exec(e)){t+=L(e.slice(n,i.index)),n=dn.lastIndex;let[a,o,s,c,l,u,d]=i;if(o)t+=`<span class="hl-c">${L(a)}</span>`;else if(s)t+=`<span class="hl-s hl-doc">${L(a)}</span>`;else if(c)t+=`<span class="hl-s">${L(a)}</span>`;else if(l)t+=`<span class="hl-d">${L(a)}</span>`;else if(u)t+=`<span class="hl-n">${L(a)}</span>`;else if(d){let e=cn.has(d)?`hl-k`:ln.has(d)?`hl-k hl-const`:r===`class`?`hl-cls`:r===`def`?`hl-f`:un.has(d)?`hl-b`:/^[A-Z]\w*$/.test(d)&&d.length>1&&/[a-z]/.test(d)?`hl-t`:``;t+=e?`<span class="${e}">${L(d)}</span>`:L(d),r=d;continue}/^\s*$/.test(a)||(r=``)}return t+L(e.slice(n))}function pn(e){let t=/("(?:[^"\\\n]|\\.)*")(\s*:)?|\b(true|false|null)\b|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)/g,n=``,r=0;for(let i=t.exec(e);i;i=t.exec(e)){n+=L(e.slice(r,i.index)),r=t.lastIndex;let[,a,o,s,c]=i;n+=a?o?`<span class="hl-key">${L(a)}</span>${L(o)}`:`<span class="hl-s">${L(a)}</span>`:s?`<span class="hl-k hl-const">${s}</span>`:`<span class="hl-n">${c??``}</span>`}return n+L(e.slice(r))}var mn={py:`python`,python:`python`,json:`json`,jsonc:`json`};function hn(e){let t=String(e||``).toLowerCase();return mn[t.replace(/^.*\./,``)]||mn[t]||``}function gn(e,t){let n=hn(t);return n===`python`?fn(e):n===`json`?pn(e):L(e)}function _n(e){return e.replace(/`([^`\n]+)`/g,`<code>$1</code>`).replace(/\*\*([^*\n]+)\*\*/g,`<b>$1</b>`).replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g,`$1<i>$2</i>`).replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g,`<a class="lnk" href="$2" target="_blank" rel="noopener">$1</a>`)}function vn(e){let t=[],n=0;for(;;){let r=e.indexOf("```",n);if(r<0)return t.push({t:`text`,s:e.slice(n)}),t;t.push({t:`text`,s:e.slice(n,r)});let i=e.indexOf(`
`,r+3),a=e.slice(r+3,i<0?e.length:i).trim(),o=i<0?e.length:i+1,s=e.indexOf("```",o);if(s<0)return t.push({t:`code`,s:e.slice(o),lang:a}),t;t.push({t:`code`,s:e.slice(o,s),lang:a}),n=s+3}}var yn=/^\s*\|.*\|\s*$/;function bn(e){return vn(String(e||``)).map(e=>{if(e.t===`code`)return`<pre><code class="hl">${gn(e.s,e.lang)}</code></pre>`;let t=L(e.s).split(`
`),n=[];for(let e=0;e<t.length;e++){let r=t[e]??``,i;if(i=r.match(/^(#{1,6})\s+(.*)$/))n.push(`<div class="md-h md-h${Math.min(i[1].length,4)}">${_n(i[2])}</div>`);else if(/^\s*(-{3,}|\*{3,})\s*$/.test(r))n.push(`<hr class="md-hr">`);else if(i=r.match(/^\s*&gt;\s?(.*)$/))n.push(`<div class="md-q">${_n(i[1])}</div>`);else if(i=r.match(/^\s*[-*]\s+(.*)$/))n.push(`<div class="md-li">${_n(i[1])}</div>`);else if(i=r.match(/^\s*(\d+)[.)]\s+(.*)$/))n.push(`<div class="md-li md-ol"><span class="md-n">${i[1]}.</span>${_n(i[2])}</div>`);else if(yn.test(r)&&/^\s*\|[\s:|-]+\|\s*$/.test(t[e+1]??``)){let i=e=>e.trim().replace(/^\||\|$/g,``).split(`|`).map(e=>_n(e.trim())),a=i(r);e+=2;let o=[];for(;e<t.length&&yn.test(t[e]??``);)o.push(i(t[e++]??``));e--,n.push(`<table class="md-t"><tr>${a.map(e=>`<th>${e}</th>`).join(``)}</tr>`+o.map(e=>`<tr>${e.map(e=>`<td>${e}</td>`).join(``)}</tr>`).join(``)+`</table>`)}else n.push(r.trim()===``?`<div class="md-gap"></div>`:`<div class="md-p">${_n(r)}</div>`)}return n.join(``)}).join(``)}function xn(e,t){let n=String(e||``),r=n.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/),i=``,a=n;if(r){a=r[2]??``;let e=(r[1]??``).split(`
`).map(e=>e.match(/^([\w-]+):\s*(.*)$/)).filter(e=>!!e).map(([,e,t])=>`<tr><td class="jmono">${L(e)}</td><td>${L(t)}</td></tr>`).join(``);i=e?`<table class="md-front">${e}</table>`:``}let o=bn(a);return`<div class="md-doc">${i}${t?t(o):o}</div>`}function Sn(e){return Cn(L(e))}var Cn=e=>e.replace(/\$\{?([A-Za-z_]\w*)\}?/g,`<span class="pv">$&</span>`).replace(/\{\{contract\}\}/g,`<span class="pv pc">{{contract}}</span>`);function wn(e){let t=e.match(/^(TELEMETRY [^\n]*)\n+([\s\S]*)$/);return t?{telemetry:t[1]??``,body:t[2]??``}:{telemetry:``,body:e}}var z=k`
  ${k`
  :host {
    --bg: var(--ca-bg, #060a11);
    --card: var(--ca-card, #0f1724);
    --panel: var(--ca-panel, #0f1724);
    --panel2: var(--ca-panel2, #142034);
    --raise: var(--ca-raise, #1a2740);
    --line: var(--ca-line, #1d2940);
    --line2: var(--ca-line2, #2b3c58);
    --fg: var(--ca-fg, #e7edf5);
    --fg2: var(--ca-fg2, #bcc7d6);
    --mut: var(--ca-mut, #8492a8);
    --muted: var(--ca-muted, #94a3b8);
    --ok: var(--ca-ok, #34d399);
    --warn: var(--ca-warn, #fbbf24);
    --err: var(--ca-err, #f87171);
    --info: var(--ca-info, #60a5fa);
    --live: var(--ca-live, #22d3ee);
    --llm: var(--ca-llm, #a78bfa);
    --ok-a: var(--ca-ok-a, rgba(52, 211, 153, 0.13));
    --live-a: var(--ca-live-a, rgba(34, 211, 238, 0.13));
    --llm-a: var(--ca-llm-a, rgba(167, 139, 250, 0.15));
    --warn-a: var(--ca-warn-a, rgba(251, 191, 36, 0.13));
    --err-a: var(--ca-err-a, rgba(248, 113, 113, 0.13));
    --muted-a: var(--ca-muted-a, rgba(148, 163, 184, 0.12));
    --well: var(--ca-well, #0a111c);
    --track: var(--ca-track, #1b273b);
    --tok-input: var(--ca-tok-input, #60a5fa);
    --tok-cache-read: var(--ca-tok-cache-read, #475569);
    --tok-cache-write: var(--ca-tok-cache-write, #fbbf24);
    --tok-output: var(--ca-tok-output, #a78bfa);
    --sans: var(--ca-sans, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif);
    --mono: var(--ca-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace);
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    color: var(--fg);
  }
  :host([hidden]) {
    display: none !important;
  }
`}
  *, *::before, *::after { box-sizing: border-box; }
  * { scrollbar-width: thin; scrollbar-color: #2b3c58 transparent; }
  *:hover { scrollbar-color: #3d5478 transparent; }
  button { font: inherit; color: inherit; }
  [hidden] { display: none !important; }

  .jmono, code, .mono { font-family: var(--mono); }
  /* read by screen readers, not shown: the word beside a status mark or an icon */
  .sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .jmono { font-size: 11.5px; }
  .meta { color: var(--mut); font-size: 11px; }
  /* a label in a tight box: it wraps at spaces and between phrases, never inside a word (Japanese included) */
  .words { word-break: keep-all; overflow-wrap: break-word; line-break: strict; }
  /* one fact of a row in .words (factLine): the line breaks between facts first, inside one only when it is wider than the box */
  .words .f { display: inline-block; max-width: 100%; }
  @supports (word-break: auto-phrase) {
    .words:lang(ja) { word-break: auto-phrase; }
  }
  .mut, .jdim { color: var(--mut); }
  .v-ok { color: var(--ok); }
  .v-bad { color: var(--err); }
  .v-mut { color: var(--mut); }
  a.lnk { color: var(--live); cursor: pointer; text-decoration: none; }
  a.lnk:hover { text-decoration: underline; }

  .pill { border-radius: 999px; padding: 1px 10px; font-size: 11px; font-weight: 500; background: var(--raise); color: var(--fg2); white-space: nowrap; }
  /* a task's status (Outcome): one colour per status, always with its word */
  .o-done, .o-recovered { background: var(--ok-a); color: var(--ok); }
  .o-failed { background: var(--err-a); color: var(--err); }
  .o-not_started { background: var(--warn-a); color: var(--warn); }
  .o-running { background: var(--live-a); color: var(--live); }
  .o-waiting, .o-skipped { background: var(--muted-a); color: var(--muted); }
  .p-completed { background: var(--ok-a); color: var(--ok); }
  .p-invalid_input { background: var(--warn-a); color: var(--warn); }
  .p-invalid_output { background: var(--err-a); color: var(--err); }
  .p-skipped { background: var(--muted-a); color: var(--muted); }
  .p-running { background: var(--live-a); color: var(--live); }
  .p-timeout, .p-max_turns, .p-stalled { background: var(--warn-a); color: var(--warn); }
  .p-error, .p-launch_failed, .p-no_output, .p-aborted { background: var(--err-a); color: var(--err); }

  .jstop { font-weight: 600; }
  .jstop.j-completed { color: #57ab5a; }
  .jstop.j-timeout { color: #d29922; }
  .jstop.j-error, .jstop.j-launch_failed, .jstop.j-no_output { color: #e5534b; }
  .jstop.j-invalid_input { color: var(--warn); }

  .dot { width: 8px; height: 8px; border-radius: 50%; background: #3b4760; flex: none; display: inline-block; }
  .dot.live { background: var(--live); animation: breathe 1.8s ease-in-out infinite; }
  .dot.ok { background: var(--ok); }
  .dot.warn { background: var(--warn); }
  .dot.err { background: var(--err); }
  .dot.llm { background: var(--llm); }
  .spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid rgba(34, 211, 238, 0.25);
    border-top-color: var(--live); animation: turn 0.9s linear infinite; flex: none; display: inline-block; }
  .kbd { font-family: var(--mono); font-size: 10px; border: 1px solid var(--line2); border-bottom-width: 2px;
    border-radius: 4px; padding: 0 4px; color: var(--mut); }

  .tag { font-size: 10px; padding: 0 7px; border-radius: 999px; border: 1px solid var(--line2); color: var(--mut); white-space: nowrap; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chip { font-size: 11px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--line); color: var(--mut); white-space: nowrap; }
  .chip.done { color: var(--ok); border-color: rgba(52, 211, 153, 0.5); }
  .chip.cur { background: var(--live); color: #03222a; border-color: var(--live); font-weight: 600; animation: ping 1.6s var(--ease) infinite; }
  .chip.todo { opacity: 0.65; }
  .taskchip { display: inline-block; font: inherit; font-family: var(--mono); font-size: 11px; line-height: 1.5; padding: 0 8px;
    border-radius: 999px; border: 1px solid var(--line); background: var(--raise); color: var(--fg2); white-space: nowrap; }
  button.taskchip { cursor: pointer; }
  button.taskchip:hover { border-color: var(--line2); color: var(--fg); }

  .g12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 14px; }
  .c12 { grid-column: span 12; }
  .c7 { grid-column: span 7; }
  .c5 { grid-column: span 5; }
  @media (max-width: 1150px) {
    .c7, .c5 { grid-column: span 12; }
  }
  .panel { background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
    border-radius: 12px; padding: 14px 16px; min-width: 0; box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28); }
  .panel > h3 { margin: 0 0 12px; display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 600; color: var(--fg2); }
  .panel > h3 .r { margin-left: auto; font-weight: 400; font-size: 11.5px; color: var(--mut); }
  .enter { animation: enter 0.5s var(--ease) both; }
  .sect-h { margin: 14px 0 8px; font-size: 12px; color: var(--fg2); font-weight: 600; }
  .sect-h .meta { margin-left: 8px; font-weight: 400; }

  .blank { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 60px 16px; color: var(--mut); text-align: center; }
  .blank .ic { font-size: 30px; opacity: 0.55; }
  .blank b { color: var(--fg2); font-weight: 600; }
  .blank a.lnk { text-decoration: underline; }
  .blank.small { padding: 24px; }

  /* a short clickable row (failures, launches) */
  .fl { padding: 7px 10px; border-radius: 8px; cursor: pointer; display: grid; grid-template-columns: auto 1fr auto; gap: 2px 10px; align-items: baseline; }
  .fl > .meta:last-child { grid-column: 1 / 4; overflow: hidden; text-overflow: ellipsis; }
  .fl:hover { background: var(--raise); }
  .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11px; color: var(--mut); }
  .legend > span { white-space: nowrap; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }

  /* who ran it: an agent launch or Python */
  .k-ic { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; margin-right: 7px;
    font-size: 11px; background: var(--muted-a); color: var(--muted); flex: none; }
  .k-ic.llm { background: var(--llm-a); color: var(--llm); }
  .jdur { position: relative; display: block; height: 6px; border-radius: 3px; background: var(--track); overflow: hidden; margin-top: 2px; }
  .jdur i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--muted); }
  .jdur i.llm { background: var(--llm); }
  .jdur i.bad { background: var(--err); }

  /* contracts */
  .ct-chip { display: inline-block; padding: 1px 10px; border-radius: 999px; font-size: 11.5px; background: var(--raise); color: var(--fg2); white-space: nowrap; }
  .ct-chip b { margin-left: 4px; }
  .ct-chip.valid { background: var(--ok-a); color: var(--ok); }
  .ct-chip.invalid, .ct-chip.failed { background: var(--err-a); color: var(--err); }
  .ct-chip.running { background: var(--live-a); color: var(--live); }
  .ct-chip.pending { background: var(--muted-a); color: var(--muted); }
  .ct-chip.refused { background: var(--warn-a); color: var(--warn); }
  .ct-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .drv-facts { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; font-size: 12px; }
  .drv-facts i { font-style: normal; color: var(--mut); margin-right: 5px; font-size: 11px; }

  @keyframes turn { to { transform: rotate(360deg); } }
  @keyframes breathe {
    0%, 100% { opacity: 0.45; box-shadow: 0 0 0 0 rgba(34, 211, 238, 0); transform: scale(0.85); }
    50% { opacity: 1; box-shadow: 0 0 0 4px rgba(34, 211, 238, 0.18); transform: scale(1); }
  }
  @keyframes ping { 0% { box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.55); } 80%, 100% { box-shadow: 0 0 0 9px rgba(34, 211, 238, 0); } }
  @keyframes enter { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  @keyframes bump { 0% { transform: scale(1); } 35% { transform: scale(1.04); box-shadow: 0 0 0 1px var(--live); } 100% { transform: scale(1); } }
  @keyframes scan { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
  @keyframes growx { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  @keyframes stripes { to { background-position: 17px 0; } }
  @keyframes toast-in { from { opacity: 0; transform: translateY(12px) scale(0.97); } to { opacity: 1; transform: none; } }
  @keyframes toast-out { to { opacity: 0; transform: translateX(24px); } }
  @keyframes rowin { from { background: rgba(34, 211, 238, 0.18); } to { background: transparent; } }
  @keyframes bounce { 0%, 80%, 100% { transform: translateY(0); opacity: 0.45; } 40% { transform: translateY(-5px); opacity: 1; } }
  @keyframes core-beat { 0%, 100% { transform: scale(1); } 50% { transform: scale(0.72); } }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }
`,Tn=k`
  .jtree { font-family: var(--mono); font-size: 12px; overflow: auto; }
  .jt { margin-left: 16px; }
  details.jt > summary { cursor: pointer; list-style: revert; }
  .jk { color: var(--info); }
  .js { color: var(--ok); }
  .jn { color: var(--warn); }

  .md-p { margin: 0.15em 0; }
  .md-gap { height: 0.5em; }
  .md-h { font-weight: 600; margin: 0.7em 0 0.25em; }
  .md-h1 { font-size: 1.25em; }
  .md-h2 { font-size: 1.12em; }
  .md-h3 { font-size: 1.03em; color: var(--fg2); }
  .md-h4 { color: var(--fg2); }
  .md-li { padding-left: 16px; text-indent: -12px; margin: 0.1em 0; }
  .md-li::before { content: '• '; color: var(--mut); }
  .md-ol::before { content: ''; }
  .md-n { color: var(--mut); margin-right: 6px; }
  .md-q { border-left: 3px solid var(--line2); padding-left: 10px; color: var(--fg2); margin: 0.2em 0; }
  .md-hr { border: 0; border-top: 1px solid var(--line); margin: 0.7em 0; }
  .md-t { border-collapse: collapse; margin: 0.4em 0; }
  .md-t th, .md-t td { border: 1px solid var(--line); padding: 3px 9px; text-align: left; font-size: 12.5px; }
  .md-t th { background: var(--raise); }
  .md-doc { padding: 10px 14px; background: var(--well); border: 1px solid var(--line); border-radius: 8px; max-height: 460px; overflow: auto; line-height: 1.55; }
  .md-doc code, .tx code { background: var(--raise); border-radius: 4px; padding: 0 4px; font-size: 0.92em; }
  .md-doc pre { background: #070d16; border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; white-space: pre-wrap; }
  .md-doc pre code, .tx pre code { background: none; padding: 0; border-radius: 0; font-size: inherit; }
  .md-front { margin-bottom: 10px; border-collapse: collapse; }
  .md-front td { padding: 2px 14px 2px 0; font-size: 12.5px; border: 0; vertical-align: top; }
  .md-front td:first-child { color: var(--mut); }
  .md-tele { color: var(--mut); font-size: 11.5px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .df-text { background: var(--well); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; font-size: 12px;
    white-space: pre-wrap; max-height: 420px; overflow: auto; margin: 0; }
  .df-tog { margin-left: auto; font-size: 11px; color: var(--live); border: 1px solid var(--line2); border-radius: 999px;
    padding: 0 9px; cursor: pointer; background: none; }
  .df-tog:hover { background: var(--live-a); }
  .pv { color: var(--live); background: var(--live-a); border-radius: 4px; padding: 0 3px; }
  .pv.pc { color: var(--llm); background: var(--llm-a); }

  .hl { font-family: var(--mono); }
  .hl-k { color: #c4a5ff; }
  .hl-const { color: #ff9e64; font-style: italic; }
  .hl-s { color: #7ee2a8; }
  .hl-doc { color: #6fcf97; font-style: italic; }
  .hl-c { color: #6b7a90; font-style: italic; }
  .hl-n { color: #f5c26b; }
  .hl-d { color: #7dd3fc; }
  .hl-f { color: #7dd3fc; font-weight: 600; }
  .hl-cls { color: #ffd479; font-weight: 700; }
  .hl-t { color: #ffd479; }
  .hl-b { color: #79b8ff; }
  .hl-key { color: #79b8ff; }
`,B=e=>(t,n)=>{n===void 0?customElements.define(e,t):n.addInitializer(()=>{customElements.define(e,t)})},En={attribute:!0,type:String,converter:Qe,reflect:!1,hasChanged:$e},Dn=(e=En,t,n)=>{let{kind:r,metadata:i}=n,a=globalThis.litPropertyMetadata.get(i);if(a===void 0&&globalThis.litPropertyMetadata.set(i,a=new Map),r===`setter`&&((e=Object.create(e)).wrapped=!0),a.set(n.name,e),r===`accessor`){let{name:r}=n;return{set(n){let i=t.get.call(this);t.set.call(this,n),this.requestUpdate(r,i,e,!0,n)},init(t){return t!==void 0&&this.C(r,void 0,e,t),t}}}if(r===`setter`){let{name:r}=n;return function(n){let i=this[r];t.call(this,n),this.requestUpdate(r,i,e,!0,n)}}throw Error(`Unsupported decorator location: `+r)};function V(e){return(t,n)=>typeof n==`object`?Dn(e,t,n):((e,t,n)=>{let r=t.hasOwnProperty(n);return t.constructor.createProperty(n,e),r?Object.getOwnPropertyDescriptor(t,n):void 0})(e,t,n)}function H(e){return V({...e,state:!0,attribute:!1})}var On=(e,t,n)=>(n.configurable=!0,n.enumerable=!0,Reflect.decorate&&typeof t!=`object`&&Object.defineProperty(e,t,n),n);function kn(e,t){return(n,r,i)=>{let a=t=>t.renderRoot?.querySelector(e)??null;if(t){let{get:e,set:t}=typeof r==`object`?n:i??(()=>{let e=Symbol();return{get(){return this[e]},set(t){this[e]=t}}})();return On(n,r,{get(){let n=e.call(this);return n===void 0&&(n=a(this),(n!==null||this.hasUpdated)&&t.call(this,n)),n}})}return On(n,r,{get(){return a(this)}})}}function U(e,t,n,r){var i=arguments.length,a=i<3?t:r===null?r=Object.getOwnPropertyDescriptor(t,n):r,o;if(typeof Reflect==`object`&&typeof Reflect.decorate==`function`)a=Reflect.decorate(e,t,n,r);else for(var s=e.length-1;s>=0;s--)(o=e[s])&&(a=(i<3?o(a):i>3?o(t,n,a):o(t,n))||a);return i>3&&a&&Object.defineProperty(t,n,a),a}var An=e=>typeof e!=`object`||!e||(Array.isArray(e)?!e.length:!Object.keys(e).length),jn=class extends M{constructor(...e){super(...e),this.open=1}static{this.styles=[z,Tn]}render(){return A`<div class="jtree">${this.node(this.value,0)}</div>`}node(e,t){if(typeof e!=`object`||!e)return A`<span class=${typeof e==`string`?`js`:`jn`}>${JSON.stringify(e)??`undefined`}</span>`;let n=Array.isArray(e)?e.map((e,t)=>[t,e]):Object.entries(e);return n.length?A`${n.map(([e,n])=>An(n)?A`<div class="jt"><span class="jk">${e}</span>: ${this.node(n,t+1)}</div>`:A`<details class="jt" ?open=${t<this.open}>
            <summary>
              <span class="jk">${e}</span>
              <span class="meta">${Array.isArray(n)?`[${n.length}]`:`{${Object.keys(n).length}}`}</span>
            </summary>
            ${this.node(n,t+1)}
          </details>`)}`:Array.isArray(e)?`[]`:`{}`}};U([V({attribute:!1})],jn.prototype,`value`,void 0),U([V({type:Number})],jn.prototype,`open`,void 0),jn=U([B(`ca-json-tree`),D()],jn);var Mn=new Set,Nn=null;function Pn(){for(let e of Mn)e.requestUpdate()}var Fn=class{constructor(e){this.host=e,e.addController(this)}hostConnected(){Mn.add(this.host),Nn??=setInterval(Pn,1e3)}hostDisconnected(){Mn.delete(this.host),!Mn.size&&Nn&&(clearInterval(Nn),Nn=null)}},In=new class{constructor(){this.seen=new Map}at(e,t,n=Date.now()){let r=Math.round(n-t*1e3),i=this.seen.get(e);return i!==void 0&&Math.abs(i-r)<5e3?i:(this.seen.set(e,r),r)}},Ln=class extends M{constructor(){super(),this.since=0,new Fn(this)}createRenderRoot(){return this}render(){return this.since?N((Date.now()-this.since)/1e3):``}};U([V({type:Number})],Ln.prototype,`since`,void 0),Ln=U([B(`ca-elapsed`)],Ln);var Rn=()=>globalThis.matchMedia?.(`(prefers-reduced-motion: reduce)`).matches??!1,zn=class extends M{constructor(...e){super(...e),this.value=0,this.shown=0,this.frame=0}createRenderRoot(){return this}willUpdate(e){if(!e.has(`value`))return;let t=this.shown,n=this.value;if(cancelAnimationFrame(this.frame),Rn()||t===n||!Number.isFinite(n)||!this.isConnected){this.shown=n;return}let r=performance.now(),i=e=>{let a=Math.min(1,(e-r)/700);this.shown=Math.round(t+(n-t)*(1-(1-a)**3)),a<1&&(this.frame=requestAnimationFrame(i))};this.frame=requestAnimationFrame(i)}disconnectedCallback(){super.disconnectedCallback(),cancelAnimationFrame(this.frame),this.shown=this.value}render(){return String(this.shown)}};U([V({type:Number})],zn.prototype,`value`,void 0),U([H()],zn.prototype,`shown`,void 0),zn=U([B(`ca-count`)],zn);var Bn={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Vn=e=>(...t)=>({_$litDirective$:e,values:t}),Hn=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}},Un=class extends Hn{constructor(e){if(super(e),this.it=j,e.type!==Bn.CHILD)throw Error(this.constructor.directiveName+`() can only be used in child bindings`)}render(e){if(e===j||e==null)return this._t=void 0,this.it=e;if(e===Tt)return e;if(typeof e!=`string`)throw Error(this.constructor.directiveName+`() called with a non-string value`);if(e===this.it)return this._t;this.it=e;let t=[e];return t.raw=t,this._t={_$litType$:this.constructor.resultType,strings:t,values:[]}}};Un.directiveName=`unsafeHTML`,Un.resultType=1;var Wn=Vn(Un),Gn=class extends M{constructor(...e){super(...e),this.text=``,this.mark=``,this.source=!1}static{this.styles=[z,Tn,k`
      :host { display: block; }
      .bar { display: flex; justify-content: flex-end; margin-bottom: 4px; }
    `]}render(){let{telemetry:e,body:t}=wn(this.text),n=xn(t,this.mark===`instructions`?Cn:void 0);return A`<div class="bar">
        <button type="button" class="df-tog" @click=${()=>this.source=!this.source}>
          ${this.source?w(`Show rendered`):w(`Show source`)}</button>
      </div>
      ${this.source?A`<pre class="df-text">${this.text}</pre>`:A`${e?A`<div class="md-tele jmono">${e}</div>`:j}${Wn(n)}`}`}};U([V()],Gn.prototype,`text`,void 0),U([V()],Gn.prototype,`mark`,void 0),U([H()],Gn.prototype,`source`,void 0),Gn=U([B(`ca-markdown`),D()],Gn);var Kn=new Set([`instructions`,`schema`,`agent`]),qn=e=>{let t=e.split(`/`).filter(Boolean);return t.length>2?`…/${t.slice(-2).join(`/`)}`:e},Jn=class extends M{constructor(...e){super(...e),this.definition=null,this.memory=`definition`,this.open=new b(`definition:open`),this.source=new b(`definition:source`)}static{this.styles=[z,Tn,k`
      :host { display: block; }
      .ct-in { display: flex; align-items: center; gap: 10px; padding: 5px 4px; border-top: 1px solid var(--line); }
      .df { border-top: 1px solid var(--line); }
      .df > summary { cursor: pointer; padding: 6px 2px; display: flex; gap: 10px; align-items: center; list-style: none; }
      .df > summary::-webkit-details-marker { display: none; }
      .df > summary::before { content: '▸'; color: var(--mut); width: 10px; transition: transform 0.15s; }
      .df[open] > summary::before { transform: rotate(90deg); }
      .py-sig { font-family: var(--mono); font-size: 14px; padding: 10px 14px; background: var(--well); border: 1px solid var(--line);
        border-radius: 8px; overflow-x: auto; white-space: pre; }
      .py-where { margin: 6px 2px 12px; font-family: var(--mono); font-size: 11.5px; color: var(--mut); overflow-wrap: anywhere; }
      .py-doc { margin: 0 0 12px; padding: 8px 12px; border-left: 3px solid var(--line2); color: var(--fg2); white-space: pre-wrap; line-height: 1.6; }
      .src { display: grid; grid-template-columns: auto minmax(0, 1fr); background: var(--well); border: 1px solid var(--line);
        border-radius: 8px; font-family: var(--mono); font-size: 12px; line-height: 1.55; max-height: 520px; overflow: auto; }
      .src pre { margin: 0; padding: 10px 12px; white-space: pre; }
      .src .ln { color: var(--mut); text-align: right; user-select: none; border-right: 1px solid var(--line); opacity: 0.7; }
    `]}willUpdate(e){e.has(`memory`)&&(this.open=new b(`${this.memory}:open`),this.source=new b(`${this.memory}:source`))}render(){let e=this.definition;if(!e)return A`<div class="blank"><span class="ic" aria-hidden="true">⌘</span><b>${w(`No definition`)}</b></div>`;if(e.executor===`python`)return this.python(e);let t=e.plugin_dirs||[],n=[[w(`Role`),e.role||w(`none`)],[t.length>1?w(`Plugin directories`):w(`Plugin directory`),t.length?A`${t.map((e,t)=>A`${t?`, `:``}<span class="jmono" title=${e}>${qn(e)}</span>`)}`:w(`none`)],[w(`Parameters`),e.params||w(`none`)],[w(`Output`),e.output||w(`none`)],...(e.validators||[]).length?[[w(`Other checks`),(e.validators||[]).join(`, `)]]:[]],r=Array.isArray(e.declared)?e.declared:[],i=t=>t.part===`agent`&&!!e.role&&t.path.replace(/^.*\//,``)===`${e.role}.md`,a=[...e.files||[]].sort((e,t)=>Number(i(t))-Number(i(e)));return A`<div class="drv-facts" style="margin-bottom:10px">${n.map(([e,t])=>A`<span><i>${e}</i>${t}</span>`)}</div>
      ${r.length?A`<h4 class="sect-h">${w(`Checked files`)}</h4>
            ${r.map(e=>A`<div class="ct-in">
                <span class="ct-chip ${e.io===`output`?`valid`:`pending`}">${e.io}</span><span class="jmono">${e.path}</span>
                <span class="meta" title=${w(`The schema the file is checked against`)}>${w(S`Schema ${e.schema}`)}</span>
              </div>`)}`:j}
      ${a.length?A`<h4 class="sect-h">${w(`Files`)}</h4>${a.map(t=>this.file(t,i(t),!!e.role))}`:A`<div class="meta">${w(A`No files | defined in Python code (<code>TaskAdapter</code>)`)}</div>`}`}python(e){let t=(e.files||[]).find(e=>e.part===`source`),n=e.line??1,r=t?t.text.replace(/\n$/,``).split(`
`).length:0,i=[[w(`Parameters`),e.params&&e.params!==`none`?e.params:w(`none`)],[w(`Output`),e.output&&e.output!==`none`?e.output:w(`none`)],...(e.validators||[]).length?[[w(`Other checks`),(e.validators||[]).join(`, `)]]:[]];return A`${e.signature?A`<div class="py-sig hl">${Wn(gn(`def ${e.signature}`,`python`))}</div>`:j}
      <div class="py-where">
        ${e.function??e.kind}${e.file?A` | <span title=${e.file}>${e.file.replace(/^.*\//,``)}${e.line?`:${e.line}`:``}</span>`:j}
      </div>
      ${e.doc?A`<div class="py-doc">${e.doc}</div>`:j}
      <div class="drv-facts" style="margin-bottom:12px">${i.map(([e,t])=>A`<span><i>${e}</i>${t}</span>`)}</div>
      ${t?A`<h4 class="sect-h">${w(`Source`)}</h4>
            <div class="src">
              <pre class="ln">${Array.from({length:r},(e,t)=>n+t).join(`
`)}</pre>
              <pre class="hl">${Wn(gn(t.text.replace(/\n$/,``),`python`))}</pre>
            </div>`:j}`}file(e,t=!1,n=!1){let r=`${e.part}|${e.path}`,i=/\.md$/i.test(e.path),a=e.part===`instructions`,o=!i||this.source.has(r),s=e.part===`agent`&&n?t:Kn.has(e.part);return A`<details class="df" ?open=${this.open.has(r)||s&&!this.open.has(`closed:${r}`)} @toggle=${e=>{let t=e.target.open;this.open.set(r,t),this.open.set(`closed:${r}`,!t)}}>
      <summary>
        <span class="tag">${e.part}</span><span class="jmono">${e.path}</span>
        ${t?A`<span class="ct-chip">${w(`Role of this kind`)}</span>`:j}
        ${i?A`<button type="button" class="df-tog" @click=${e=>{e.preventDefault(),this.source.set(r,!this.source.has(r)),this.requestUpdate()}}>${w(o?`Show rendered`:`Show source`)}</button>`:j}
      </summary>
      ${o?A`<pre class="df-text"><code class="hl">${Wn(a?Sn(e.text):gn(e.text,e.path))}</code></pre>`:Wn(xn(e.text,a?Cn:void 0))}
    </details>`}};U([V({attribute:!1})],Jn.prototype,`definition`,void 0),U([V()],Jn.prototype,`memory`,void 0),Jn=U([B(`ca-definition`),D()],Jn);var Yn=new Set([`launch`,`message_update`,`tool_execution_start`,`tool_execution_update`,`tool_execution_end`,`acall`,`aresult`,`message_start`,`message_end`,`turn_end`,`notice`,`auto_retry_start`]);function Xn(e){return Yn.has(e.type)?e:null}var Zn=/\{[^{}]+\}/g,Qn=()=>typeof process==`object`&&Number.parseInt(process?.versions?.node?.substring(0,2))>=18&&process.versions.undici;function $n(){return Math.random().toString(36).slice(2,11)}function er(e){let{baseUrl:t=``,Request:n=globalThis.Request,fetch:r=globalThis.fetch,querySerializer:i,bodySerializer:a,pathSerializer:o,headers:s,requestInitExt:c=void 0,...l}={...e};c=Qn()?c:void 0,t=lr(t);let u=[];async function d(e,d){let{baseUrl:f,fetch:p=r,Request:m=n,headers:h,params:g={},parseAs:_=`json`,querySerializer:v,bodySerializer:ee=a??or,pathSerializer:te,body:y,middleware:ne=[],...b}=d||{},x=t;f&&(x=lr(f)??t);let re=typeof i==`function`?i:ir(i);v&&(re=typeof v==`function`?v:ir({...typeof i==`object`?i:{},...v}));let ie=te||o||ar,S=y===void 0?void 0:ee(y,cr(s,h,g.header)),ae=cr(S===void 0||S instanceof FormData?{}:{"Content-Type":`application/json`},s,h,g.header),C=[...u,...ne],oe={redirect:`follow`,...l,...b,body:S,headers:ae},w,se,T=new m(sr(e,{baseUrl:x,params:g,querySerializer:re,pathSerializer:ie}),oe),E;for(let e in b)e in T||(T[e]=b[e]);if(C.length){w=$n(),se=Object.freeze({baseUrl:x,fetch:p,parseAs:_,querySerializer:re,bodySerializer:ee,pathSerializer:ie});for(let t of C)if(t&&typeof t==`object`&&typeof t.onRequest==`function`){let n=await t.onRequest({request:T,schemaPath:e,params:g,options:se,id:w});if(n){if(n instanceof m)T=n;else if(n instanceof Response){E=n;break}else throw Error(`onRequest: must return new Request() or Response() when modifying the request`)}}}if(!E){try{E=await p(T,c)}catch(t){let n=t;if(C.length)for(let t=C.length-1;t>=0;t--){let r=C[t];if(r&&typeof r==`object`&&typeof r.onError==`function`){let t=await r.onError({request:T,error:n,schemaPath:e,params:g,options:se,id:w});if(t){if(t instanceof Response){n=void 0,E=t;break}if(t instanceof Error){n=t;continue}throw Error(`onError: must return new Response() or instance of Error`)}}}if(n)throw n}if(C.length)for(let t=C.length-1;t>=0;t--){let n=C[t];if(n&&typeof n==`object`&&typeof n.onResponse==`function`){let t=await n.onResponse({request:T,response:E,schemaPath:e,params:g,options:se,id:w});if(t){if(!(t instanceof Response))throw Error(`onResponse: must return new Response() when modifying the response`);E=t}}}}let ce=E.headers.get(`Content-Length`);if(E.status===204||T.method===`HEAD`||ce===`0`&&!E.headers.get(`Transfer-Encoding`)?.includes(`chunked`))return E.ok?{data:void 0,response:E}:{error:void 0,response:E};if(E.ok)return{data:await(async()=>{if(_===`stream`)return E.body;if(_===`json`&&!ce){let e=await E.text();return e?JSON.parse(e):void 0}return await E[_]()})(),response:E};let D=await E.text();try{D=JSON.parse(D)}catch{}return{error:D,response:E}}return{request(e,t,n){return d(t,{...n,method:e.toUpperCase()})},GET(e,t){return d(e,{...t,method:`GET`})},PUT(e,t){return d(e,{...t,method:`PUT`})},POST(e,t){return d(e,{...t,method:`POST`})},DELETE(e,t){return d(e,{...t,method:`DELETE`})},OPTIONS(e,t){return d(e,{...t,method:`OPTIONS`})},HEAD(e,t){return d(e,{...t,method:`HEAD`})},PATCH(e,t){return d(e,{...t,method:`PATCH`})},TRACE(e,t){return d(e,{...t,method:`TRACE`})},use(...e){for(let t of e)if(t){if(typeof t!=`object`||!(`onRequest`in t||`onResponse`in t||`onError`in t))throw Error("Middleware must be an object with one of `onRequest()`, `onResponse() or `onError()`");u.push(t)}},eject(...e){for(let t of e){let e=u.indexOf(t);e!==-1&&u.splice(e,1)}}}}function tr(e,t,n){if(t==null)return``;if(typeof t==`object`)throw Error("Deeply-nested arrays/objects aren’t supported. Provide your own `querySerializer()` to handle these.");return`${e}=${n?.allowReserved===!0?t:encodeURIComponent(t)}`}function nr(e,t,n){if(!t||typeof t!=`object`)return``;let r=[],i={simple:`,`,label:`.`,matrix:`;`}[n.style]||`&`;if(n.style!==`deepObject`&&n.explode===!1){for(let e in t)r.push(e,n.allowReserved===!0?t[e]:encodeURIComponent(t[e]));let i=r.join(`,`);switch(n.style){case`form`:return`${e}=${i}`;case`label`:return`.${i}`;case`matrix`:return`;${e}=${i}`;default:return i}}for(let i in t){let a=n.style===`deepObject`?`${e}[${i}]`:i;r.push(tr(a,t[i],n))}let a=r.join(i);return n.style===`label`||n.style===`matrix`?`${i}${a}`:a}function rr(e,t,n){if(!Array.isArray(t))return``;if(n.explode===!1){let r={form:`,`,spaceDelimited:`%20`,pipeDelimited:`|`}[n.style]||`,`,i=(n.allowReserved===!0?t:t.map(e=>encodeURIComponent(e))).join(r);switch(n.style){case`simple`:return i;case`label`:return`.${i}`;case`matrix`:return`;${e}=${i}`;default:return`${e}=${i}`}}let r={simple:`,`,label:`.`,matrix:`;`}[n.style]||`&`,i=[];for(let r of t)n.style===`simple`||n.style===`label`?i.push(n.allowReserved===!0?r:encodeURIComponent(r)):i.push(tr(e,r,n));return n.style===`label`||n.style===`matrix`?`${r}${i.join(r)}`:i.join(r)}function ir(e){return function(t){let n=[];if(t&&typeof t==`object`)for(let r in t){let i=t[r];if(i!=null){if(Array.isArray(i)){if(i.length===0)continue;n.push(rr(r,i,{style:`form`,explode:!0,...e?.array,allowReserved:e?.allowReserved||!1}));continue}if(typeof i==`object`){n.push(nr(r,i,{style:`deepObject`,explode:!0,...e?.object,allowReserved:e?.allowReserved||!1}));continue}n.push(tr(r,i,e))}}return n.join(`&`)}}function ar(e,t){let n=e;for(let r of e.match(Zn)??[]){let e=r.substring(1,r.length-1),i=!1,a=`simple`;if(e.endsWith(`*`)&&(i=!0,e=e.substring(0,e.length-1)),e.startsWith(`.`)?(a=`label`,e=e.substring(1)):e.startsWith(`;`)&&(a=`matrix`,e=e.substring(1)),!t||t[e]===void 0||t[e]===null)continue;let o=t[e];if(Array.isArray(o)){n=n.replace(r,rr(e,o,{style:a,explode:i}));continue}if(typeof o==`object`){n=n.replace(r,nr(e,o,{style:a,explode:i}));continue}if(a===`matrix`){n=n.replace(r,`;${tr(e,o)}`);continue}n=n.replace(r,a===`label`?`.${encodeURIComponent(o)}`:encodeURIComponent(o))}return n}function or(e,t){return e instanceof FormData?e:t&&(t.get instanceof Function?t.get(`Content-Type`)??t.get(`content-type`):t[`Content-Type`]??t[`content-type`])===`application/x-www-form-urlencoded`?new URLSearchParams(e).toString():JSON.stringify(e)}function sr(e,t){let n=`${t.baseUrl}${e}`;t.params?.path&&(n=t.pathSerializer(n,t.params.path));let r=t.querySerializer(t.params.query??{});return r.startsWith(`?`)&&(r=r.substring(1)),r&&(n+=`?${r}`),n}function cr(...e){let t=new Headers;for(let n of e){if(!n||typeof n!=`object`)continue;let e=n instanceof Headers?n.entries():Object.entries(n);for(let[n,r]of e)if(r===null)t.delete(n);else if(Array.isArray(r))for(let e of r)t.append(n,e);else r!==void 0&&t.set(n,r)}return t}function lr(e){return e.endsWith(`/`)?e.substring(0,e.length-1):e}var ur=class extends Error{constructor(e,t){super(`${e} ${t}`),this.status=e,this.path=t,this.name=`ApiError`}};async function dr(e){let{data:t,response:n}=await e;if(!n.ok||t===void 0)throw new ur(n.status,new URL(n.url,`http://x`).pathname);return t}function fr(e={}){let t=(e.baseUrl??``).replace(/\/$/,``),n=er({baseUrl:t||globalThis.location?.origin||``,...e.fetch?{fetch:e.fetch}:{}});return{baseUrl:t,info:()=>dr(n.GET(`/api/info`)),runs:()=>dr(n.GET(`/api/runs`)),journal:(e,t=0)=>dr(n.GET(`/api/runs/{run}/journal`,{params:{path:{run:e},query:{since:t}}})),definitions:e=>dr(n.GET(`/api/runs/{run}/definitions`,{params:{path:{run:e}}})),task:(e,t)=>dr(n.GET(`/api/runs/{run}/task/{slot_or_key}`,{params:{path:{run:e,slot_or_key:t}}})),stream:(e,t,r=0)=>dr(n.GET(`/api/runs/{run}/stream/{key}`,{params:{path:{run:e,key:t},query:{since:r}}})),panel:(e,t)=>dr(n.GET(`/api/runs/{run}/panels/{name}`,{params:{path:{run:e,name:t}}}))}}var pr=[`journal`,`procs`,`plan`,`outputs`,`cursor`,`tasks`,`ready`];function mr(e,t,n,r){let i=new(r.EventSource??globalThis.EventSource)(e);i.onopen=()=>n.open?.(),i.onerror=()=>n.error?.();for(let e of t)i.addEventListener(e,t=>{n.message({event:e,data:JSON.parse(t.data)})});return()=>i.close()}var hr=encodeURIComponent;function gr(e,t,n,r={}){let i=[...pr,...t.map(e=>`panel:${e}`)];return mr(`${r.baseUrl??``}/events?run=${hr(e)}`,i,n,r)}function _r(e,t,n,r={}){return mr(`${r.baseUrl??``}/events/stream?run=${hr(e)}&key=${hr(t)}`,[`stream`],{...n,message:e=>n.message(e.data)},r)}var vr=4e3;function yr(){return{journal:[],tasks:[],procs:null,plan:{nodes:[],groups:[],flow_calls:[]},outputs:{contracts:[],tally:{valid:0,invalid:0,refused:0,pending:0,failed:0,running:0}},cursor:null,panels:{},ready:!1}}function br(e,t){let n=e,r=null,i=()=>{if(!r)return;let e=n.journal.concat(r);n={...n,journal:e.length>4e3?e.slice(e.length-vr):e},r=null};for(let e of t){if(e.event===`journal`){(r??=[]).push(e.data);continue}switch(i(),e.event){case`connected`:n={...n,journal:[],ready:!1};break;case`ready`:n={...n,ready:!0};break;case`procs`:n={...n,procs:e.data};break;case`tasks`:n={...n,tasks:e.data};break;case`plan`:n={...n,plan:e.data};break;case`outputs`:n={...n,outputs:e.data};break;case`cursor`:n={...n,cursor:e.data};break;default:n={...n,panels:{...n.panels,[e.event.slice(6)]:e.data}}}}return i(),n}var xr=e=>!!e.stop&&e.stop!==`completed`&&e.stop!==`skipped`,W=e=>e.executor===`python`,Sr=e=>`${e.ts}|${e.key}`,Cr=(e,t)=>e.find(e=>e.run===t),wr=(e,t)=>!!e.procs?.alive||!!t?.running;function Tr(e){return e?[...e.launches.map(e=>({cls:`llm`,id:`c:${e.key}`,kind:e.kind||`task`,unit:e.unit||``,detail:[e.unit,e.model||e.role].filter(Boolean).join(` | `),ageS:e.age_s,key:e.key})),...e.python_tasks.map(e=>({cls:`py`,id:`p:${e.key}`,kind:e.kind||`task`,unit:e.unit||``,detail:e.unit||`Python`,ageS:e.age_s,key:``}))]:[]}function Er(e){let t=e.filter(e=>!W(e)),n=t.find(e=>e.running);return n?n.slot:t.filter(e=>e.last_ts).sort((e,t)=>t.last_ts.localeCompare(e.last_ts))[0]?.slot??null}var Dr={title:`contraagent`,panels:[],api_version:``},Or=class{constructor(e={}){this.snap={info:Dr,runs:[],run:``,state:yr(),connected:!1,fresh:new Set},this.listeners=new Set,this.rowListeners=new Set,this.closeFeed=null,this.queue=[],this.flushTimer=null,this.pollTimer=null,this.opts={runsEveryMs:5e3,batchMs:50,freshMs:4e3,...e},this.client=e.client??fr(e.baseUrl===void 0?{}:{baseUrl:e.baseUrl})}get snapshot(){return this.snap}subscribe(e){return this.listeners.add(e),()=>this.listeners.delete(e)}onNewRow(e){return this.rowListeners.add(e),()=>this.rowListeners.delete(e)}async start(){try{let e=this.panelNames();this.set({info:await this.client.info()}),this.snap.run&&this.panelNames()!==e&&this.reopen()}catch{}await this.refreshRuns(),this.pollTimer??=setInterval(()=>void this.refreshRuns(),this.opts.runsEveryMs)}async refreshRuns(){try{this.set({runs:await this.client.runs()})}catch{}}panelNames(){return this.snap.info.panels.map(e=>e.name).join(`
`)}reopen(){let e=this.snap.run;this.closeFeed?.(),this.closeFeed=null,this.selectRun(e)}selectRun(e){(e!==this.snap.run||!this.closeFeed&&e)&&(this.closeFeed?.(),this.closeFeed=null,this.queue=[],this.set({run:e,state:yr(),connected:!1,fresh:new Set}),e&&(this.closeFeed=gr(e,this.snap.info.panels.map(e=>e.name),{open:()=>{this.push({event:`connected`}),this.set({connected:!0})},error:()=>this.set({connected:!1}),message:e=>this.push(e)},{...this.opts.baseUrl===void 0?{}:{baseUrl:this.opts.baseUrl},...this.opts.feed})))}stop(){this.closeFeed?.(),this.closeFeed=null,this.pollTimer&&clearInterval(this.pollTimer),this.pollTimer=null,this.flushTimer&&clearTimeout(this.flushTimer),this.flushTimer=null}push(e){this.queue.push(e),this.flushTimer??=setTimeout(()=>this.flush(),this.opts.batchMs)}flush(){this.flushTimer=null;let e=this.queue;this.queue=[];let t=this.snap.state.ready,n=[];for(let r of e)r.event===`connected`?t=!1:r.event===`ready`?t=!0:r.event===`journal`&&t&&n.push(r.data);let r=br(this.snap.state,e);if(!n.length){this.set({state:r});return}let i=new Set(this.snap.fresh);for(let e of n)i.add(Sr(e));this.set({state:r,fresh:i});for(let e of n)for(let t of this.rowListeners)t(e);setTimeout(()=>{let e=new Set(this.snap.fresh);for(let t of n)e.delete(Sr(t));this.set({fresh:e})},this.opts.freshMs)}set(e){this.snap={...this.snap,...e};for(let e of this.listeners)e(this.snap)}},kr=e=>e.ok,G=e=>e.stop!==`invalid_input`&&e.stop!==`skipped`;function Ar(e,t){if(e?.state===`running`)return`running`;let n=t[t.length-1];return n?n.stop===`skipped`?`skipped`:n.stop===`invalid_input`?`not_started`:kr(n)?t.some(e=>!kr(e))?`recovered`:`done`:`failed`:e?.state===`blocked`?`not_started`:`waiting`}function jr(e,t){let n=new Map;for(let t of e){let e=n.get(t.key);e||n.set(t.key,e=[]),e.push(t)}let r=new Map(t.nodes.map(e=>[e.key,e])),i=[...new Set([...t.nodes.map(e=>e.key),...n.keys()])],a=new Map;for(let e of i){let t=r.get(e),i=n.get(e)??[],o=i[0];a.set(e,{key:e,kind:t?.kind??o?.kind??``,unit:t?.unit??o?.unit??``,executor:t?.executor??o?.executor??`agent`,outcome:Ar(t,i),attempts:i,tries:i.filter(G),cause:null})}let o=(e,t)=>{for(let n of r.get(e)?.after??[]){if(t.has(n))continue;t.add(n);let e=a.get(n);if(e?.outcome===`failed`)return n;if(e?.outcome===`not_started`){let e=o(n,t);if(e)return e}}return null};for(let e of a.values())e.outcome===`not_started`&&(e.cause=o(e.key,new Set));return a}function Mr(e){let t=new Map;for(let n of e.values())n.outcome===`failed`&&t.set(n.key,{task:n,stopped:[]});let n=[];for(let r of e.values()){if(r.outcome!==`not_started`)continue;let e=r.cause?t.get(r.cause):void 0;e?e.stopped.push(r):n.push(r)}let r=e=>e.attempts[e.attempts.length-1]?.ts??``;return{failed:[...t.values()].sort((e,t)=>r(t.task).localeCompare(r(e.task))),notStarted:n}}function Nr(e){let t={done:0,recovered:0,failed:0,not_started:0,running:0,waiting:0,skipped:0,total:0};for(let n of e.values())t[n.outcome]++,t.total++;return t}function Pr(e){let t=Array.isArray(e?.flow)?e.flow:[];for(let e=t.length-1;e>=0;e--){let n=t[e]?.loops??[],r=n[n.length-1];if(r)return typeof r.pass==`number`&&r.pass>=1?r.pass:1}return null}var Fr=new Set([`done`,`recovered`,`skipped`]);function Ir(e,t){let n=jr(e,t),r=new Map(t.nodes.map(e=>[e.key,e]));return[...n.values()].map(e=>{let t=e.attempts[e.attempts.length-1],i=r.get(e.key);return{...e,pass:Pr(i),wall_s:e.tries.reduce((e,t)=>e+(t.wall_s||0),0),last_ts:t?.ts??``,last_stop:t?.stop??``,waits_for:e.outcome===`waiting`?(i?.after??[]).filter(e=>!Fr.has(n.get(e)?.outcome??`waiting`)):[]}})}var Lr=()=>({input:0,output:0,cache_read:0,cache_creation:0,calls:0,cost:null,reported:0}),Rr=e=>e.input+e.output+e.cache_read+e.cache_creation;function zr(e,t){let n=t.usage;return!n&&(t.cost_usd===null||t.cost_usd===void 0)?e:(n&&(e.input+=n.input??0,e.output+=n.output??0,e.cache_read+=n.cache_read??0,e.cache_creation+=n.cache_creation??0,e.calls+=n.calls??0),t.cost_usd!==null&&t.cost_usd!==void 0&&(e.cost=(e.cost??0)+t.cost_usd),e.reported++,e)}function Br(e){let t=Lr();for(let n of e)zr(t,n);return t.reported?t:null}function Vr(e,t){let n=new Map,r=Lr();for(let i of e){zr(r,i);let e=t(i),a=n.get(e);a||n.set(e,a={id:e,kind:i.kind,unit:i.unit??``,spend:Lr(),share:null}),zr(a.spend,i)}let i=[...n.values()].filter(e=>e.spend.reported);for(let e of i)e.share=r.cost?(e.spend.cost??0)/r.cost:null;return i.sort((e,t)=>(t.spend.cost??0)-(e.spend.cost??0)||Rr(t.spend)-Rr(e.spend))}var Hr=e=>Vr(e,e=>e.key),Ur=e=>Vr(e,e=>e.kind).map(e=>({...e,unit:``})),Wr=e=>Date.parse(e.observed_at??``),Gr=e=>!Number.isNaN(Wr(e))&&(e.five_hour_pct!=null||e.seven_day_pct!=null);function Kr(e){let t=[];for(let n of e)for(let e of n.quota??[])Gr(e)&&t.push({reading:e,key:n.key,attempt:n.attempt??0});return t.sort((e,t)=>Wr(e.reading)-Wr(t.reading))}function qr(e){let t=new Map;for(let{reading:n}of Kr(e)){let e=n.credential??``,r=t.get(e);r||t.set(e,r=[]),r.push(n)}let n=[];for(let[e,r]of t){let t=r[0],i=r[r.length-1];t&&i&&n.push({credential:e,first:t,last:i})}return n.sort((e,t)=>(t.last.seven_day_pct??0)-(e.last.seven_day_pct??0))}function Jr(e,t){let n=(e.quota??[]).filter(Gr).sort((e,t)=>Wr(e)-Wr(t)),r=Date.parse(e.ts),i=n[0]??null,a=i?.credential??``;return{start:i,next:(i===null||Number.isNaN(r)?void 0:t.find(e=>Wr(e.reading)>r&&(e.reading.credential??``)===a))?.reading??null}}function Yr(e){switch(e){case`done`:return w(`done`);case`recovered`:return w(`done after retrying`);case`failed`:return w(`failed`);case`not_started`:return w(`not started`);case`running`:return w(`running`);case`waiting`:return w(`waiting`);case`skipped`:return w(`skipped`)}}var Xr=(e,t)=>e===`waiting`&&!t?w(`not run`):Yr(e);function Zr(e){let t=e[0];return t?e.length===1?w(S`waits for output of ${I(t)}`):w(S`waits for output of ${e.length} earlier tasks`):``}function Qr(e,t){if(t)return t.outcome;let n=e[e.length-1];return n?n.stop===`invalid_input`?`not_started`:n.stop===`skipped`?`skipped`:n.ok?e.some(e=>G(e)&&!e.ok)?`recovered`:`done`:`failed`:`waiting`}function $r(e){switch(e){case`done`:return w(`done`);case`failed`:return w(`failed`);case`blocked`:return w(`not started`);case`running`:return w(`running`);case`pending`:return w(`waiting`);case`skipped`:return w(`skipped`)}}function K(e,t){switch(e){case`done`:return w(S`${t} done`);case`recovered`:return w(S`${t} done after retrying`);case`failed`:return w(S`${t} failed`);case`not_started`:return w(S`${t} not started`);case`running`:return w(S`${t} running`);case`waiting`:return w(S`${t} waiting`);case`skipped`:return w(S`${t} skipped`);case`not_run`:return w(S`${t} not run`)}}function q(e,t){switch(e){case`completed`:return w(`done`);case`skipped`:return w(`skipped`);case`invalid_input`:{let e=new Set(di(t).map(e=>e.problem));return e.size===1&&e.has(`missing`)?w(`not started (input missing)`):e.size===1&&e.has(`checks`)?w(`not started (input failed checks)`):w(`not started (input missing or failed checks)`)}case`invalid_output`:return w(`failed checks`);case`timeout`:return w(`timed out`);case`max_turns`:return w(`turn limit reached`);case`budget`:return w(`cost limit reached`);case`context_budget`:return w(`context limit reached`);case`stalled`:return w(`stalled (no output)`);case`auth_failed`:return w(`authentication failed`);case`api_error`:return w(`API error`);case`rate_limited`:return w(`rate limited`);case`refused`:return w(`refused by the model`);case`aborted`:return w(`aborted`);case`denied`:return w(`permission denied`);case`error`:return w(`error`);case`no_output`:return w(`ended without a result`);case`launch_failed`:return w(`could not start the agent`);case`credential_mismatch`:return w(`wrong identity used`);case null:case void 0:case``:return`—`;default:return w(S`unknown (${e})`)}}var ei=e=>w(S`Attempt ${(e??0)+1}`),ti=e=>w(S`Pass ${e}`),ni=e=>w(e<=1?`1 pass`:S`up to ${e} passes`),ri=e=>w(e<=1?`1 pass`:S`${e} passes`),ii=e=>e.map(([e,t])=>w(e<=1?S`1 pass: ${t}`:S`${e} passes: ${t}`)).join(` | `),ai=()=>w(`loop`);function oi(e){return e<=0?``:w(e===1?`1 correction`:S`${e} corrections`)}var si=e=>e?e===`ambient`?w(`default`):e:``,ci=e=>e===`ambient`?w(`local credentials (ambient)`):``,li=e=>e.model||e.route||`—`;function ui(e,t){if(!e||e.length<2)return``;let n=e.map((t,n)=>n<e.length-1?w(S`${li(t)} (${q(t.stop)})`):li(t)).join(` → `);return t==null?n:`${n} | ${N(t)}`}function di(e){let t=/^invalid input:\s*(.*)$/s.exec(e||``);if(!t)return[];let n=[];for(let e of(t[1]??``).split(`; `)){let t=/^input from (\S+) is missing: (\S+)/.exec(e);if(t){n.push({path:t[2]??``,producer:t[1]??``,problem:`missing`});continue}if(t=/^(\S+?): required input is missing/.exec(e),t){n.push({path:t[1]??``,producer:``,problem:`missing`});continue}t=/^(\S+?): /.exec(e),t&&!n.some(e=>e.path===t?.[1])&&n.push({path:t[1]??``,producer:``,problem:`checks`})}return n}function fi(e,t,n){return t===`checks`?w(n?S`input ${e} from ${n.name} failed checks`:S`input ${e} failed checks`):n?n.outcome===`failed`?w(S`input ${e} is missing because ${n.name} failed`):n.outcome===`not_started`?w(S`input ${e} is missing because ${n.name} did not start`):n.outcome===`done`||n.outcome===`recovered`||n.outcome===`skipped`?w(S`input ${e} from ${n.name} is missing`):w(S`input ${e} is missing because ${n.name} did not finish`):w(S`input ${e} is missing`)}function pi(e,t,n,r){let i=e.attempts[e.attempts.length-1];if(i?.stop===`invalid_input`){let e=di(i.reason)[0];if(!e)return J(i.reason,n);let a=e.producer||r?.(e.path)||``,o=a?t.get(a):void 0;return fi(J(e.path,n),e.problem,o?{name:I(o),outcome:o.outcome}:void 0)}let a=e.cause?t.get(e.cause):void 0;return a?w(S`earlier task ${I(a)} failed`):``}function J(e,t){if(!e||!t)return e??``;let n=t.replace(/[.*+?^${}()|[\]\\]/g,`\\$&`);return e.replace(RegExp(`(?:/[^\\s:'"]*)?/${n}/`,`g`),``)}var mi=6e3,hi=[`wheel`,`touchstart`,`pointerdown`,`keydown`],gi=class{constructor(e){this.id=e,this.el=null,this.frame=0,this.restoring=!1,this.cancel=()=>{if(cancelAnimationFrame(this.frame),this.frame=0,this.restoring){this.restoring=!1;for(let e of hi)this.el?.removeEventListener(e,this.cancel)}},this.onScroll=()=>{!this.restoring&&this.el&&y(this.id,Math.round(this.el.scrollTop))}}attach(e){this.el!==e&&(this.detach(),this.el=e,e.addEventListener(`scroll`,this.onScroll,{passive:!0}))}detach(){this.cancel(),this.el?.removeEventListener(`scroll`,this.onScroll),this.el=null}restore(){let e=this.el;if(!e)return;this.cancel();let t=te(this.id)??0;if(t<=0){e.scrollTop=0;return}let n=performance.now()+mi;this.restoring=!0;for(let t of hi)e.addEventListener(t,this.cancel,{passive:!0,once:!0});let r=()=>{let i=e.scrollHeight-e.clientHeight;if(e.scrollTop=Math.min(t,i),i>=t||performance.now()>n)return this.cancel();this.frame=requestAnimationFrame(r)};r()}reset(){this.cancel(),this.el&&(this.el.scrollTop=0)}};function _i(e){let t=e.groups.reduce((e,t)=>e+t.total,0),n=e.groups.reduce((e,t)=>e+t.done+t.skipped,0);return{total:t,done:n,pct:Math.round(100*n/Math.max(1,t))}}function vi(e){let t=e.filter(G).length;return{tries:t,notStarted:e.length-t}}function yi(e){let t=(...t)=>e.nodes.filter(e=>t.includes(e.state)).length;return{done:t(`done`,`skipped`),failed:t(`failed`),notStarted:t(`blocked`),left:t(`pending`,`running`)}}function bi(e){let t=Date.parse(e?.started_at??``),n=Date.parse(e?.last_ts??``);return Number.isNaN(t)||Number.isNaN(n)?null:Math.max(0,(n-t)/1e3)}var xi={failed:5,running:4,blocked:3,pending:2,skipped:1,done:0},Si=e=>e.reduce((e,t)=>xi[t.state]>xi[e]?t.state:e,`done`),Ci=e=>e.reduce((e,t)=>xi[t]>xi[e]?t:e,`done`),wi=`loop:`,Ti=e=>typeof e==`string`;function Ei(e){let t=e.flow;if(!Array.isArray(t))return[];let n=[];for(let e of t){let t=e;if(!t||typeof t!=`object`||!Ti(t.function))break;let r=(Array.isArray(t.loops)?t.loops:[]).filter(e=>!!e&&typeof e.line==`number`);n.push({function:t.function,file:Ti(t.file)?t.file:``,line:typeof t.line==`number`?t.line:0,loops:r.map(e=>e.line),passes:r.map(e=>typeof e.pass==`number`&&e.pass>=1?e.pass:1)})}return n}function Di(e){let t=e.flow_calls;return!Array.isArray(t)||t.length===0?null:new Map(t.filter(e=>e&&Ti(e.id)&&Ti(e.function)).map(e=>[e.id,e]))}var Oi=new WeakMap;function ki(e){let t=Oi.get(e);if(t)return t;let n=e.nodes.map(e=>{let t=Ei(e),n=e.created_from;return{n:e,frames:t,path:t.map(e=>e.function),from:Array.isArray(n)?n.filter(Ti):[],call:Ti(e.flow_call)?e.flow_call:``}}),r=new Map;for(let t of e.nodes)t.unit&&!r.has(t.unit)&&r.set(t.unit,r.size);let i={tasks:n,byKey:new Map(n.map(e=>[e.n.key,e])),calls:Di(e),unitRank:r,labels:new Map(e.groups.map(e=>[e.id,e.label]))};return Oi.set(e,i),i}var Ai=(e,t)=>t.every((t,n)=>e[n]===t),ji=e=>e.slice(e.lastIndexOf(`.`)+1)||e,Mi=(e,t)=>t>0?e.frames[t-1]?.loops??[]:[],Ni=(e,t)=>t>0?e.frames[t-1]?.passes??[]:[];function Pi(e,t){for(let n=0;n<Math.max(e.length,t.length);n++){let r=(e[n]??0)-(t[n]??0);if(r)return r}return 0}var Fi=e=>e.map((t,n)=>`${wi}${e.slice(0,n+1).join(`.`)}`);function Ii(e,t){let n=Mi(e,t),r=n.length?`@${n.join(`.`)}`:``;if(e.path.length<=t)return{id:`kind:${e.n.group}${r}`,type:`kind`,name:e.n.group,loops:n};let i=e.path[t];return{id:`flow:${i}${r}`,type:`flow`,name:i,loops:n}}function Li(e,t,n){if(!e.call)return{id:`>${t}`,own:!1};let r=e.call.split(`.`),i=r.map((e,t)=>r.slice(0,t+1).join(`.`)),a=0,o=0;if(n)for(let r=1;r<i.length;r++){let s=n.get(i[r])?.function,c=s===void 0?-1:e.frames.findIndex((e,t)=>t>o&&e.function===s);if(c<0||c>t)break;a=r,o=c}else a=Math.min(t,i.length-1),o=a;let s=i[a];return o===t?{id:s,own:!0}:{id:`${s}>${t}`,own:!1}}var Ri={running:`running`,returned:`done`,raised:`failed`,closed:`failed`},zi=e=>e?.state===`raised`||e?.state===`closed`;function Bi(e,t){let n=e.map(e=>e.n);return{key:(n.find(e=>e.state===`running`)??n[n.length-1]??{key:``}).key,unit:t,state:Si(n),count:n.length,keys:n.map(e=>e.key)}}var Vi=(e,t,n)=>{let r=e.get(t);r?r.push(n):e.set(t,[n])};function Hi(e){let t=new Map,n=[];for(let r of e)r.n.unit?Vi(t,r.n.unit,r):n.push(Bi([r],``));return{byUnit:new Map([...t].map(([e,t])=>[e,Bi(t,e)])),single:n}}function Ui(e,t,n){let r=new Map;for(let i of e){let{id:e,own:a}=Li(i,t,n);(r.get(e)??r.set(e,{id:e,own:a,tasks:[],unit:``}).get(e))?.tasks.push(i)}for(let e of r.values()){let t=new Set(e.tasks.map(e=>e.n.unit||``));e.unit=t.size===1?[...t][0]:``}return[...r.values()]}function Wi(e,t,n,r){let i=(e,t)=>{let i=e.map(e=>e.own?r?.get(e.id):void 0),a=e.map((e,t)=>{let n=i[t],r=Si(e.tasks.map(e=>e.n));return n&&Ri[n.state]?Ci([Ri[n.state],r]):r}),o=e.flatMap(e=>e.tasks),s=o.map(e=>e.n.key),c=e.find((e,t)=>a[t]===`running`)??e[e.length-1],l=i.find(zi),u={key:c?.id??``,unit:t,state:Ci(a),count:s.length,keys:s,flow:n,counts:Gi(o)};return l?{...u,error:l.error??``}:u},a=new Map,o=[],s=Ui(e,t,r);for(let e of s)e.unit?Vi(a,e.unit,e):o.push(i([e],``));let c=r?s.filter(e=>e.own&&zi(r.get(e.id))).length:0;return{byUnit:new Map([...a].map(([e,t])=>[e,i(t,e)])),single:o,calls:s.length,errors:c}}function Gi(e){let t={total:e.length,done:0,failed:0,running:0,pending:0,skipped:0,blocked:0};for(let n of e)t[n.n.state]+=1;return t}function Ki(e,t){let n=new Map;for(let r of e){let e=r.n.unit||``,i=n.get(e);(!i||Pi(Ni(r,t),i)>0)&&n.set(e,Ni(r,t))}return e.filter(e=>Pi(Ni(e,t),n.get(e.n.unit||``)??[])===0)}function qi(e,t){let n=new Map;for(let r of e){let e=r.n.unit||``;(n.get(e)??n.set(e,new Set).get(e))?.add(Ni(r,t).join(`.`))}return new Map([...n].map(([e,t])=>[e,t.size]))}var Ji=(e,t)=>t&&t>1?{...e,passes:t}:e,Yi=(e,t)=>`${e}\u0000${t}`;function Xi(e,t,n){let r=new Set(e),i=new Map(e.map(e=>[e,[]]));for(let[e,n]of t)e!==n&&r.has(e)&&r.has(n)&&!i.get(e)?.includes(n)&&i.get(e)?.push(n);let a=new Set,o=new Map;for(let t of e){if(o.has(t))continue;o.set(t,1);let e=[[t,0]];for(;e.length;){let t=e[e.length-1],n=i.get(t[0])??[];if(t[1]<n.length){let r=n[t[1]++],i=o.get(r);i===1?a.add(Yi(t[0],r)):i||(o.set(r,1),e.push([r,0]))}else o.set(t[0],2),e.pop()}}let s=new Map(e.map(e=>[e,[]])),c=new Map(e.map(e=>[e,[]]));for(let[e,t]of i)for(let n of t)a.has(Yi(e,n))||(s.get(e)?.push(n),c.get(n)?.push(e));let l=new Map(e.map(e=>[e,c.get(e)?.length??0])),u=e.filter(e=>!l.get(e)),d=new Map;for(let e=u.shift();e!==void 0;e=u.shift()){d.set(e,n.get(e)??Math.max(0,...(c.get(e)??[]).map(e=>(d.get(e)??0)+1)));for(let t of s.get(e)??[])l.set(t,(l.get(t)??0)-1),l.get(t)||u.push(t)}return d}function Zi(e,t,n,r){let i=0,a=new Map;for(let[e,i]of t){let t=r.get(e);t!==void 0&&Vi(a,t,[n.get(e)??0,n.get(i)??0])}for(let e of a.values())for(let t=0;t<e.length;t++)for(let n=t+1;n<e.length;n++){let[r,a]=e[t],[o,s]=e[n];(r-o)*(a-s)<0&&i++}return e.length?i:0}var Y=e=>e.startsWith(`~`);function Qi(e,t,n){let r=new Map;e.forEach((e,t)=>e.forEach(e=>r.set(e,t)));let i=new Map,a=new Map;for(let[e,n]of t)Vi(a,e,n),Vi(i,n,e);let o=new Map,s=e=>e.forEach((e,t)=>o.set(e,t)),c=e.map(e=>[...e]);c.forEach(s);let l=()=>Zi(c,t,o,r),u=c.map(e=>[...e]),d=l(),f=(e,t)=>{let r=new Map;for(let n of e){let e=(t.get(n)??[]).map(e=>o.get(e)).filter(e=>e!==void 0);r.set(n,e.length?e.reduce((e,t)=>e+t,0)/e.length:o.get(n)??0)}let i=e=>r.get(e)??0;if(!n)return[...e].sort((e,t)=>i(e)-i(t)||(o.get(e)??0)-(o.get(t)??0));let a=e.filter(e=>!Y(e)),s=e.filter(Y).sort((e,t)=>i(e)-i(t)||(o.get(e)??0)-(o.get(t)??0)),c=[],l=0;for(let e of a){for(;l<s.length&&i(s[l])<i(e);)c.push(s[l++]);c.push(e)}return[...c,...s.slice(l)]};for(let e=0;e<4;e++){let t=e%2==0,n=t?c.map((e,t)=>t).slice(1):c.map((e,t)=>t).reverse().slice(1);for(let e of n){let n=f(c[e],t?i:a);c[e]=n,s(n)}let r=l();r<d&&(d=r,u=c.map(e=>[...e]))}return l()<=d?c:u}function $i(e,t,n,r=!1){let i=ki(e),a=t.length,o=i.tasks.filter(e=>Ai(e.path,t)),s=new Map,c=new Map;for(let e of o){let t=Ii(e,a);(s.get(t.id)??s.set(t.id,{...t,tasks:[]}).get(t.id))?.tasks.push(e),c.set(e.n.key,t.id)}let l=new Map,u=new Map,d=new Map,f=new Map;for(let e of s.values()){let t=Fi(e.loops),n=t[t.length-1]??null;t.forEach((e,n)=>f.set(e,t[n-1]??null)),n&&d.set(e.id,n);let r=n?Ki(e.tasks,a):e.tasks;u.set(e.id,r);let o=e.type===`kind`?Hi(r):Wi(r,a,e.name,i.calls);if(n){let t=qi(e.tasks,a);o.byUnit=new Map([...o.byUnit].map(([e,n])=>[e,Ji(n,t.get(e))]))}l.set(e.id,o)}let p=[...new Set([...l.values()].flatMap(e=>[...e.byUnit.keys()]))].sort((e,t)=>(i.unitRank.get(e)??0)-(i.unitRank.get(t)??0)),m=new Map,h=new Map;for(let e of s.values()){let t=Fi(e.loops);for(let n of e.tasks){let e=Ni(n,a);t.forEach((t,r)=>{m.set(t,Math.max(m.get(t)??1,e[r]??1));let i=h.get(t)??h.set(t,new Map).get(t),a=n.n.unit||``;(i?.get(a)??i?.set(a,new Set).get(a))?.add(e.slice(0,r+1).join(`.`))})}}let g=e=>{let t=[],n=e.startsWith(`loop:`)?e:d.get(e)??null;for(;n;)t.push(n),n=f.get(n)??null;return t},_=(e,t)=>{let n=g(e);if(t===``)return n[n.length-1]??e;let r=n.indexOf(t);return r<0?void 0:r===0?e:n[r-1]},v=(e,t)=>g(e).find(e=>g(t).includes(e))??``,ee=e=>e.startsWith(`stub:`)?``:d.get(e)??``,te=new Set,y=new Map,ne=new Map,b=e=>{let n=0;for(;n<a&&e.path[n]===t[n];)n++;let r=Ii(e,n);return{id:`stub:${n}:${r.id}`,label:r.type===`kind`?i.labels.get(r.name)??r.name:ji(r.name)}};for(let e of o){let t=c.get(e.n.key),n=(n,r)=>{let o=c.get(n);if(o===t){r===`after`&&te.add(t);return}if(o!==void 0){let s=i.byKey.get(n),c=Mi(s,a),l=Mi(e,a),u=0;for(;u<c.length&&c[u]===l[u];)u++;let d=Pi(Ni(s,a).slice(0,u),Ni(e,a).slice(0,u))===0,f=`${o}\u0000${t}\u0000${r}`,p=y.get(f)??y.set(f,{from:o,to:t,type:r,tasks:new Set,samePass:!1}).get(f);p?.tasks.add(e.n.key),p&&d&&(p.samePass=!0);return}let s=i.byKey.get(n);if(!s)return;let l=b(s),u=`${l.id}\u0000${t}\u0000${r}`;(ne.get(u)??ne.set(u,{...l,to:t,type:r,tasks:new Set}).get(u))?.tasks.add(e.n.key)};for(let t of e.n.after??[])n(t,`after`);for(let t of e.from)n(t,`created`)}let x=[...y.values()].filter(e=>e.type===`after`||!y.has(`${e.from}\u0000${e.to}\u0000after`)),re=[...ne.values()].filter(e=>e.type===`after`||!ne.has(`${e.id}\u0000${e.to}\u0000after`)),ie=[``,...f.keys()],S=new Map(ie.map(e=>[e,[]]));for(let e of s.keys())for(let t of ie){let n=_(e,t);n!==void 0&&!S.get(t)?.includes(n)&&S.get(t)?.push(n)}let ae=new Map;for(let e of ie){let t=S.get(e)??[],r=e===``?n?.layers:n?.boxes[e],i=new Map;r?.forEach((e,n)=>e.forEach(e=>t.includes(e)&&i.set(e,n)));let a=x.filter(t=>t.samePass&&v(t.from,t.to)===e).map(t=>[_(t.from,e),_(t.to,e)]);ae.set(e,Xi(t,a,i))}let C=ae.get(``),oe=[...new Set(re.map(e=>e.id))],w=new Map;n?.layers.forEach((e,t)=>e.forEach(e=>w.set(e,t)));let se=new Map(oe.map(e=>[e,w.get(e)??Math.min(...re.filter(t=>t.id===e).map(e=>C.get(_(e.to,``))??0))-1]));if([...se.values()].some(e=>e<0)){for(let[e,t]of C)C.set(e,t+1);for(let[e,t]of se)se.set(e,t+1)}for(let[e,t]of se)C.set(e,t);let T=(e,t)=>ae.get(e)?.get(t)??0,E=e=>Math.max(0,...ae.get(e)?.values()??[]),ce=(e,t)=>{let n=v(e,t);return T(n,_(e,n))>=T(n,_(t,n))},D=x.map(e=>({from:e.from,to:e.to,tasks:e.tasks.size,type:e.type,back:ce(e.from,e.to)})),le=new Map;for(let e of ie){let t=((e===``?n?.layers:n?.boxes[e])??[]).flat(),r=[...e===``?[...oe]:[],...S.get(e)??[]];r.sort((e,n)=>{let r=t.indexOf(e),i=t.indexOf(n);return(r<0?1/0:r)-(i<0?1/0:i)});let i=Array.from({length:E(e)+1},()=>[]);for(let t of r)i[T(e,t)]?.push(t);le.set(e,i)}let O=[],ue=new Set,de=(e,t,n,r)=>{let i=`~${e}|${t}|${n}|${r}`;return ue.has(i)||(ue.add(i),le.get(e)?.[r]?.push(i)),{id:i,in:e}},fe=(e,t,n,r)=>{let i=T(e,t),a=`~${e}|by:${t}|${n}|${r}|${i}`;return ue.has(a)||(ue.add(a),le.get(e)?.[i]?.push(a)),{id:a,in:e}},pe=(e,t,n)=>{let i=e.startsWith(`stub:`)?``:v(e,t),a=ee(e),o=e,s=[{id:e,in:a}];for(;a!==i;){let e=f.get(a)??``;s.push({id:a,in:e}),T(a,o)<E(a)&&s.push(fe(e,a,o,n)),o=a,a=e}let c=_(t,i);for(let e=T(i,o)+1;e<T(i,c);e++)s.push(de(i,o,n,e));let l=g(t),u=l.slice(0,i===``?l.length:l.indexOf(i)).reverse(),d=`>${i}:${o}`,p=i;for(let e of u){let i=_(t,e);(T(e,i)>0||r)&&s.push(fe(p,e,d,n)),s.push({id:e,in:p}),p=e}return s.push({id:t,in:p}),s};for(let e of D)e.back||O.push({from:e.from,to:e.to,type:e.type,steps:pe(e.from,e.to,e.type)});for(let e of re)O.push({from:e.id,to:e.to,type:e.type,steps:pe(e.id,e.to,e.type)});let me={};for(let e of ie){let t=[],r=new Map((le.get(e)??[]).flatMap((e,t)=>e.map(e=>[e,t])));for(let n of O)for(let i=1;i<n.steps.length;i++){let a=n.steps[i-1],o=n.steps[i];a.in===e&&o.in===e&&r.get(a.id)!==r.get(o.id)&&t.push([a.id,o.id])}let i=e===``?!!n:!!n?.boxes[e];me[e]=Qi(le.get(e)??[],t,i).map(e=>{let t=e.filter(e=>e.includes(`|by:`));return e.filter(e=>!e.includes(`|by:`)).flatMap(e=>[e,...t.filter(t=>t.includes(`|by:${e}|`))])})}let he=e=>e.map(e=>e.filter(e=>!Y(e))),ge=[...f.keys()].map(e=>{let t=new Map;for(let[n,r]of h.get(e)??[])n&&t.set(r.size,(t.get(r.size)??0)+1);return{id:e,loop:Number(e.slice(5).split(`.`).pop()),file:o[0]?.frames[a-1]?.file??``,parent:f.get(e)??null,passes:m.get(e)??1,spread:[...t].sort((e,t)=>e[0]-t[0]),layers:he(me[e]??[]).filter(e=>e.length)}}),_e=he(me[``]??[]).map(e=>e.filter(e=>!e.startsWith(`stub:`))),ve=e=>{let t=l.get(e.id),n=t.byUnit.size>0;return{id:e.id,type:e.type,name:e.name,label:e.type===`kind`?i.labels.get(e.name)??e.name:ji(e.name),kinds:[...new Set(e.tasks.map(e=>e.n.kind))],box:d.get(e.id)??null,units:n?p.map(e=>t.byUnit.get(e)??null):[],single:t.single,inOrder:te.has(e.id),counts:Gi(u.get(e.id)??[]),calls:t.calls??0,errors:t.errors??0}},ye=new Map(ge.map(e=>[e.id,e])),be=e=>e.flatMap(e=>e.startsWith(`loop:`)?be((ye.get(e)?.layers??[]).flat()):[e]);return{graph:{path:[...t],nodes:be(_e.flat()).map(e=>ve(s.get(e))),layers:_e.filter(e=>e.length),boxes:ge,edges:D,stubs:re.map(e=>({id:e.id,label:e.label,to:e.to,tasks:e.tasks.size,type:e.type})),units:p,slots:me,routes:O,order:{layers:he(me[``]??[]),boxes:Object.fromEntries(ge.map(e=>[e.id,he(me[e.id]??[])]))}},drafts:s,ix:i}}function ea(e,t=[],n,r=!1){return $i(e,t,n,r).graph}function ta(e){let t=ki(e),n=[],r=new Set;if(t.calls)for(let e of t.calls.values())(e.state===`raised`||e.state===`closed`)&&r.add(e.id);let i=e=>r.has(e)&&![...r].some(t=>t!==e&&t.startsWith(`${e}.`));for(;;){let e=null,r=!0,a=[];for(let i of t.tasks){if(!Ai(i.path,n))continue;let t=Ii(i,n.length);if(t.type===`kind`||e&&e.id!==t.id){r=!1;break}e=t,a.push(i)}let o=a.some(e=>i(Li(e,n.length,t.calls).id));if(!r||!e||o)return n;n.push(e.name)}}function na(e){let t=e[e.length-1];return t?.startsWith(`loop:`)?{path:e.slice(0,-1),loop:t}:{path:[...e],loop:null}}function ra(e,t){if(e.length<=t.length)return null;let n=e.slice(0,-1);return n.length<=t.length?[]:n}function ia(e,t,n,r){let{graph:i,drafts:a,ix:o}=$i(e,t,r),s=i.boxes.find(e=>e.id===n);if(!s)return null;let c=t.length,l=s.id.slice(5).split(`.`).length-1,u=new Map(i.boxes.map(e=>[e.id,e])),d=new Map(i.nodes.map(e=>[e.id,e])),f=e=>Ni(e,c).slice(l),p=e=>e.layers.flat().flatMap(e=>u.has(e)?p(u.get(e)):[e]),m=e=>p(e).flatMap(e=>a.get(e)?.tasks??[]),h=(e,t)=>e.length===t.length&&Pi(e,t)===0,g=(e,t)=>{let n=t.length;return[...new Set(m(e).map(f).filter(e=>e.length>n&&Pi(e.slice(0,n),t)===0).map(e=>e[n]))].sort((e,t)=>e-t).flatMap(n=>{let r=[...t,n],i=e.layers.flat().flatMap(e=>{let t=u.get(e);if(t){let e=g(t,r);return e.length?[{type:`loop`,box:t,kids:e}]:[]}let n=d.get(e);return n&&a.get(e)?.tasks.some(e=>h(f(e),r))?[{type:`node`,node:n,passes:r}]:[]});return i.length?[{type:`pass`,box:e,pass:n,kids:i}]:[]})},_=g(s,[]),v=[],ee=e=>e.type===`node`?1:e.kids.reduce((e,t)=>e+ee(t),0),te=e=>e.type===`node`?1:1+Math.max(0,...e.kids.map(te)),y=Math.max(1,..._.map(te)),ne=Array.from({length:y},()=>[]),b=(e,t)=>{let n=ne[t];if(e.type===`node`){n.push({type:`node`,node:e.node,passes:e.passes,span:1,rows:y-t}),v.push({node:e.node,passes:e.passes});return}n.push(e.type===`pass`?{type:`pass`,box:e.box,pass:e.pass,span:ee(e),rows:1}:{type:`loop`,box:e.box,span:ee(e),rows:1});for(let n of e.kids)b(n,t+1)};for(let e of _)b(e,0);let x=m(s),re=new Set(x.map(e=>e.n.unit||``)),ie=[...i.units.filter(e=>re.has(e)),...re.has(``)?[``]:[]],S=new Map;v.forEach((e,t)=>{for(let n of a.get(e.node.id)?.tasks??[])h(f(n),e.passes)&&Vi(S,`${t}\u0000${n.n.unit||``}`,n)});let ae=(e,t,n)=>{let r=a.get(e.node.id);if(r.type===`kind`)return Bi(t,n);let i=Wi(t,c,r.name,o.calls);return n?i.byUnit.get(n)??i.single[0]??null:i.single[0]??null};return{box:s,columns:v,head:ne,rows:ie.map(e=>{let t=v.map((t,n)=>{let r=S.get(`${n}\u0000${e}`);return r?.length?ae(t,r,e):null});return{unit:e,passes:new Set(x.filter(t=>(t.n.unit||``)===e).map(e=>Ni(e,c).slice(0,l+1).join(`.`))).size,state:Ci(t.filter(e=>e!==null).map(e=>e.state)),cells:t}})}}function aa(e,t){let n=new Map(e.map((e,t)=>[e,t])),r=e=>t===`passes`?-e.passes:t===`state`?-xi[e.state]:0;return[...e].sort((e,t)=>r(e)-r(t)||(n.get(e)??0)-(n.get(t)??0))}function oa(e,t,n,r,i=!1,a=10){let o=(t,n)=>e[t]?.[n]===!0,s=t=>(e[t]??[]).findIndex(Boolean),c=t=>(e[t]??[]).lastIndexOf(!0),l=(t,n,r)=>{for(let i=t;i>=0&&i<e.length;i+=n)if(o(i,r))return i;return-1},u=t=>{let r=e[t]??[],i=-1;return r.forEach((e,t)=>e&&(i<0||Math.abs(t-n)<Math.abs(i-n))&&(i=t)),i<0?null:[t,i]};switch(r){case`ArrowRight`:case`ArrowLeft`:{let i=r===`ArrowRight`?1:-1;for(let r=n+i;r>=0&&r<(e[t]?.length??0);r+=i)if(o(t,r))return[t,r];return null}case`ArrowDown`:case`ArrowUp`:{let i=r===`ArrowDown`?1:-1,a=l(t+i,i,n);if(a>=0)return[a,n];for(let n=t+i;n>=0&&n<e.length;n+=i)if(s(n)>=0)return u(n);return null}case`Home`:{let n=i?e.findIndex(e=>e.some(Boolean)):t;return n<0||s(n)<0?null:[n,s(n)]}case`End`:{let n=t;if(i)for(n=e.length-1;n>=0&&c(n)<0;n--);return n<0||c(n)<0?null:[n,c(n)]}case`PageDown`:case`PageUp`:{let n=r===`PageDown`?1:-1,i=Math.max(0,Math.min(e.length-1,t+n*a));for(let e=i;e!==t;e-=n)if(s(e)>=0)return u(e);return null}default:return null}}function sa(e){return e<=12?{cols:Math.max(1,e),size:12}:e<=100?{cols:10,size:10}:{cols:20,size:6}}var ca=e=>e.units.filter(e=>e!==null).length+e.single.length>200;function la(e,t){return t.filter(t=>e[t]>0).map(t=>({state:t,n:e[t],pct:100*e[t]/Math.max(1,e.total)}))}function ua(e,t,n,r){let i=new Map(e.nodes.map((e,t)=>[e.id,t])),a=[...new Set(e.edges.filter(e=>!e.back&&(n===`later`?e.from===t:e.to===t)).map(e=>n===`later`?e.to:e.from))],o=r(t);return a.sort((e,t)=>Math.abs(r(e)-o)-Math.abs(r(t)-o)||(i.get(e)??0)-(i.get(t)??0)),a[0]??null}var da={across:{gap:56,boxGap:40,sep:16,pointSep:12,pad:12,padEnd:16,margin:16},down:{gap:40,boxGap:32,sep:16,pointSep:12,pad:10,padEnd:16,margin:16}};function fa(e,t,n){let r=[0];for(let n=1;n<e.length;n++)r.push(r[n-1]+t[n-1]);let i=[];e.forEach((e,t)=>{let a=n[t]??1;for(i.push({sum:a*(e-r[t]),w:a,n:1});i.length>1;){let e=i[i.length-1],t=i[i.length-2];if(t.sum/t.w<=e.sum/e.w)break;i.splice(-2,2,{sum:t.sum+e.sum,w:t.w+e.w,n:t.n+e.n})}});let a=[];for(let e of i)for(let t=0;t<e.n;t++)a.push(e.sum/e.w+r[a.length]);return a}function pa(e,t,n=!1){let r=da[n?`down`:`across`],i=e=>n?e.h:e.w,a=e=>n?e.w:e.h,o=new Set(e.boxes.map(e=>e.id)),s=e=>t.get(`lbl:${e}`)??{w:0,h:0},c=e=>n?{u0:s(e).h+r.pad+r.gap/2,u1:r.pad,v0:r.pad,v1:r.padEnd,minU:0,minV:s(e).w+2*r.pad}:{u0:r.pad,u1:r.pad,v0:s(e).h+r.pad,v1:r.padEnd,minU:s(e).w+2*r.pad,minV:0},l=new Map,u=e=>{if(o.has(e))return l.get(e)??{u:0,v:0};if(Y(e))return{u:0,v:0};let n=t.get(e)??{w:0,h:0};return{u:i(n),v:a(n)}},d=new Map,f=new Map,p=e=>e===``?0:e.split(`.`).length,m=[``,...e.boxes.map(e=>e.id)].sort((e,t)=>p(t)-p(e)),h=(t,n)=>{let r=e.routes[t]?.steps??[],i=r[n];if(Y(i.id))return 0;if(!o.has(i.id))return u(i.id).v/2;let a=r[n-1]?.in===i.id?n-1:n+1,s=r[a];return c(i.id).v0+(d.get(i.id)?.top.get(s.id)??0)+h(t,a)};for(let t of m){let n=(e.slots[t]??[]).map(e=>[...e]);f.set(t,new Map(n.flatMap((e,t)=>e.map(e=>[e,t]))));let i=n.map(e=>Math.max(0,...e.map(e=>u(e).u))),a=t===``?r.gap:r.boxGap,s=[];i.forEach((e,t)=>s.push(t?s[t-1]+i[t-1]+a:0));let p=[];e.routes.forEach((e,n)=>e.steps.forEach((r,i)=>{let a=e.steps[i-1];i&&a&&a.in===t&&r.in===t&&f.get(t)?.get(a.id)!==f.get(t)?.get(r.id)&&p.push({a:a.id,b:r.id,oa:h(n,i-1),ob:h(n,i)})}));let m=(e,t)=>t===void 0?0:o.has(e)||o.has(t)||!(Y(e)||Y(t))?r.sep:r.pointSep,g=new Map;for(let e of n){let t=0;e.forEach((n,r)=>{g.set(n,t),t+=u(n).v+m(n,e[r+1])})}let _=(e,t)=>{let n=e.map(e=>{let n=t(e);return n.length?n.reduce((e,t)=>e+t,0)/n.length:g.get(e)??0}),r=e.map((t,n)=>u(t).v+m(t,e[n+1])),i=e.map((e,t)=>Y(e)?-1:t).filter(e=>e>=0),a=(e,t)=>r.slice(e,t).reduce((e,t)=>e+t,0),o=fa(i.map(e=>n[e]),i.map((e,t)=>t+1<i.length?a(e,i[t+1]):0),i.map(()=>1));i.forEach((e,t)=>n[e]=o[t]),fa(n,r,e.map(e=>Y(e)?1:1e6)).forEach((t,n)=>g.set(e[n],Math.round(t*100)/100))},v=(e,t)=>{let n=Y(e)?t:t.filter(e=>!Y(e.other));return(n.length?n:t).map(e=>e.at)},ee=e=>v(e,p.filter(t=>t.b===e).map(e=>({other:e.a,at:(g.get(e.a)??0)+e.oa-e.ob}))),te=e=>v(e,p.filter(t=>t.a===e).map(e=>({other:e.b,at:(g.get(e.b)??0)+e.ob-e.oa})));for(let e=0;e<8;e++){let t=n.map((e,t)=>t);e%2&&t.reverse();for(let r of t)_(n[r],e%2?te:ee)}for(let e of n)_(e,e=>[...ee(e),...te(e)]);let y=g.size?Math.min(...g.values()):0;for(let[e,t]of g)g.set(e,t-y);let ne=(s[s.length-1]??0)+(i[i.length-1]??0),b=Math.max(0,...n.flat().map(e=>(g.get(e)??0)+u(e).v));if(d.set(t,{rows:n,start:s,width:i,top:g,u:ne,v:b}),t!==``){let e=c(t);l.set(t,{u:Math.max(e.u0+ne+e.u1,e.minU),v:Math.max(e.v0+b+e.v1,e.minV)})}}let g={},_=new Map,v=(e,t,r)=>n?{x:t,y:e,w:r.v,h:r.u}:{x:e,y:t,w:r.u,h:r.v},ee=(e,t,n)=>{_.set(e,{u:t,v:n});let r=d.get(e);r.rows.forEach((e,i)=>e.forEach(e=>{if(Y(e))return;let a=t+r.start[i],s=n+(r.top.get(e)??0);if(g[e]=v(a,s,u(e)),o.has(e)){let t=c(e);ee(e,a+t.u0,s+t.v0)}}))};ee(``,r.margin,r.margin);let te=d.get(``),y=te.u+2*r.margin,ne=te.v+2*r.margin,b=(e,t)=>{let n=d.get(e),r=(_.get(e)??{u:0,v:0}).u+(n.start[t]??0);return[r,r+(n.width[t]??0)]},x=(e,t)=>f.get(e)?.get(t)??0,re=e=>e&&Y(e.id)?/\|by:([^|]*)\|/.exec(e.id)?.[1]??``:``,ie=e.routes.map((e,t)=>{let i=n=>{let r=e.steps[n];return(_.get(r.in)??{u:0,v:0}).v+(d.get(r.in)?.top.get(r.id)??0)+h(t,n)},a=e.steps.map((t,a)=>{let o=e.steps[a-1],l=e.steps[a+1],[f,p]=b(t.in,x(t.in,t.id)),m=i(a);if(a===0)return{a:f+u(t.id).u,b:p,at:m};if(a===e.steps.length-1)return{a:f,b:f,at:m};if(Y(t.id)){let i=re(t);if(i&&o?.id===i)return{a:b(i,x(i,e.steps[a-2]?.id??``)+1)[0],b:p,at:m};if(i&&l?.id===i){let t=x(i,e.steps[a+2]?.id??``);return{a:f,b:t>0?b(i,t-1)[1]:(g[i]?n?g[i].y:g[i].x:f)+s(i).h+r.pad,at:m}}return{a:f,b:p,at:m}}let h=c(t.id),_=d.get(t.id);if(o?.in===t.id){if(re(l)===t.id){let e=b(t.id,x(t.id,o.id)+1)[0];return{a:e,b:e,at:i(a+1)}}return{a:f+h.u0+_.u,b:p,at:m}}if(re(o)===t.id){let e=b(t.id,x(t.id,l?.id??``))[0];return{a:e,b:e,at:i(a+1)}}return{a:f,b:f+h.u0,at:m}});return{from:e.from,to:e.to,type:e.type,runs:a}});return{w:n?ne:y,h:n?y:ne,at:g,edges:ie,down:n}}function ma(e,t=!1){let n=e=>Math.round(e*2)/2,r=(e,r)=>t?`${n(r)},${n(e)}`:`${n(e)},${n(r)}`,i=e[0];if(!i)return``;let a=`M${r(i.a,i.at)}`;return e.forEach((t,n)=>{t.b!==t.a&&(a+=` L${r(t.b,t.at)}`);let i=e[n+1];if(!i)return;if(Math.abs(i.at-t.at)<.5){i.a!==t.b&&(a+=` L${r(i.a,i.at)}`);return}let o=(t.b+i.a)/2;a+=` C${r(o,t.at)} ${r(o,i.at)} ${r(i.a,i.at)}`}),a}function ha(e,t,n,r){if(e<=0||t<=0||n<=0)return{k:1,x:0,y:0,h:Math.max(0,t)};let i=Math.min(1,n/e),a=Math.min(t*i,r),o=Math.min(i,a/t);return{k:o,x:(n-e*o)/2,y:(a-t*o)/2,h:a}}function ga(e,t,n,r,i,a){let o=Math.min(a,Math.max(i,e.k*t)),s=o/e.k;return{k:o,x:n-(n-e.x)*s,y:r-(r-e.y)*s}}function _a(e){let t=e.filter(G),n=t.filter(W),r=t.filter(e=>!W(e)),i=e=>e.reduce((e,t)=>e+(t.wall_s||0),0),a=e=>[...new Set(e.map(e=>e.key))],o=e=>a(e).length,s=t.filter(e=>(e.attempt??0)>0),c=t.filter(e=>(e.rounds||1)>1),l=t.filter(e=>(e.hops||[]).length>1);return{attempts:t.length,python:n.length,launches:r.length,bad:t.filter(e=>!e.ok).length,launchWall:i(r),pythonWall:i(n),retries:s.length,retriedTasks:o(s),retriedKeys:a(s),fixupKeys:a(c),fixups:c.reduce((e,t)=>e+(t.rounds||1)-1,0),fixupTasks:o(c),switches:l.reduce((e,t)=>e+(t.hops||[]).length-1,0),switchTasks:o(l)}}var va=216e5,ya=6e4;function ba(e,t,n){let r=[];for(let t of e){if(!t.ts)continue;let e=Date.parse(t.ts);if(Number.isNaN(e))continue;let n=G(t)?t.ok?W(t)?`py`:`llm`:`bad`:`idle`;r.push({lane:t.kind||`?`,cls:n,start:e-(t.wall_s||0)*1e3,end:e,live:!1,row:t})}if(!r.length&&!t.length)return null;for(let e of t)r.push({lane:e.kind,cls:`run`,start:e.t0,end:n,live:!0,liveCls:e.cls});let i=Math.max(...r.filter(e=>!e.live).map(e=>e.end),...t.map(e=>e.t0)),a=r.filter(e=>e.end>=i-va),o=Math.min(...a.map(e=>e.start)),s=t.length?o+Math.ceil((n-o+2e4)/ya)*ya:i,c=[];for(let e of[...a].sort((e,t)=>e.start-t.start))c.includes(e.lane)||c.push(e.lane);let l=c.map(e=>{let t=a.filter(t=>t.lane===e).sort((e,t)=>e.start-t.start),n=[],r=t.map(({cls:e,start:t,end:r,live:i,row:a})=>{let o=n.findIndex(e=>e<=t);return o<0?o=n.push(r)-1:n[o]=r,a?{cls:e,start:t,end:r,live:i,track:o,row:a}:{cls:e,start:t,end:r,live:i,track:o}});return{name:e,llm:t.some(e=>e.cls===`llm`||e.liveCls===`llm`),bars:r,tracks:Math.max(1,n.length)}});return{t0:o,span:Math.max(1,s-o),lanes:l,hidden:r.length-a.length,live:t.length>0}}function xa(e,t,n){let r=(e.start-t.t0)/t.span*100,i=((e.live?n:e.end)-e.start)/t.span*100;return{left:r,width:Math.max(.4,e.live?Math.min(100-r,i):i)}}var Sa=e=>e==null?`—`:`${Math.round(e)}%`;function Ca(e){if(!e||e===`allowed`)return``;let t=e.split(`,`);return t.some(e=>[`rejected`,`exhausted`,`quota`,`blocked`].includes(e))?w(`limit reached`):t.every(e=>[`allowed_warning`,`warning`].includes(e))?w(`near the limit`):w(S`unknown (${e})`)}function wa(e,t=Date.now()){let n=Date.parse(e??``);if(Number.isNaN(n))return``;if(n<=t)return w(`reset`);let r=(n-t)/36e5,i=r>=48?w(S`${Math.floor(r/24)}d ${Math.floor(r%24)}h`):N((n-t)/1e3);return w(S`resets in ${i}`)}var Ta=e=>F(w(S`weekly ${Sa(e.seven_day_pct)}`),w(S`5-hour ${Sa(e.five_hour_pct)}`));function Ea(e){let t=[e.seven_day_resets_at?w(S`Weekly usage ${Sa(e.seven_day_pct)} (resets ${P(e.seven_day_resets_at,!0)})`):w(S`Weekly usage ${Sa(e.seven_day_pct)}`),e.five_hour_resets_at?w(S`5-hour usage ${Sa(e.five_hour_pct)} (resets ${P(e.five_hour_resets_at,!0)})`):w(S`5-hour usage ${Sa(e.five_hour_pct)}`),w(S`Reported ${P(e.observed_at,!0)}`)],n=Ca(e.status);return n&&t.push(w(S`Status: ${n}`)),t.join(`
`)}var Da=e=>F(Ta(e),si(e.credential));function Oa(e){let t=e[0];if(!t)return``;let n=e.length-1;return n?F(Da(t.last),w(n===1?`1 more account`:S`${n} more accounts`)):Ta(t.last)}var ka=e=>e.map(e=>e.credential?`${si(e.credential)}\n${Ea(e.last)}`:Ea(e.last)).join(`

`);function Aa(e,t,r){return r.key?A`<button type="button" class="taskchip" title=${r.key} @click=${t=>{t.stopPropagation(),n(e,`ca-open-task`,{key:r.key,...W(r)?{view:`output`}:{}})}}>${t}</button>`:A`<span class="taskchip">${t}</span>`}var ja=e=>bi(e),Ma=e=>{let t=Date.parse(e.last_ts||``);return Number.isNaN(t)?1/0:(Date.now()-t)/1e3},Na=class extends M{constructor(...e){super(...e),this.runs=[],this.current=``,this.open=!1,this.q=``,this.kb=-1}static{this.styles=[z,k`
      :host { position: absolute; top: 50px; width: min(580px, calc(100vw - 24px)); max-height: min(72vh, 660px);
        display: flex; flex-direction: column; background: var(--panel); border: 1px solid var(--line2); border-radius: 14px;
        box-shadow: 0 24px 70px rgba(0, 0, 0, 0.65); opacity: 0; transform: translateY(-6px) scale(0.985);
        pointer-events: none; z-index: 40; transition: opacity 0.16s var(--ease), transform 0.16s var(--ease); }
      :host([open]) { opacity: 1; transform: none; pointer-events: auto; }
      .search { padding: 10px; border-bottom: 1px solid var(--line); }
      input { width: 100%; background: var(--well); border: 1px solid var(--line); color: var(--fg); border-radius: 9px;
        padding: 8px 11px; font: inherit; outline: none; }
      input:focus { border-color: var(--live); }
      .list { overflow: auto; padding: 6px; }
      .group { font-size: 11.5px; font-weight: 600; color: var(--mut); padding: 10px 9px 4px; }
      .group .n { font-weight: 400; margin-left: 4px; }
      .keys { margin-top: 6px; display: flex; gap: 4px; align-items: center; }
      .item { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; gap: 3px 10px; align-items: center;
        padding: 7px 9px; border-radius: 9px; cursor: pointer; }
      .item:hover, .item.kb { background: var(--raise); }
      .item.cur { box-shadow: inset 2px 0 0 var(--live); background: var(--live-a); }
      .nm { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .when { font-size: 11px; color: var(--mut); white-space: nowrap; }
      .sub { grid-column: 2 / 4; display: flex; gap: 7px; flex-wrap: wrap; font-size: 11px; color: var(--mut); }
    `]}updated(e){e.has(`open`)&&this.open&&(this.q=``,this.kb=-1,setTimeout(()=>this.input?.focus(),30))}visible(){let e=this.q.toLowerCase().trim(),t=this.runs.filter(t=>!e||t.run.toLowerCase().includes(e)||(t.run_group||``).toLowerCase().includes(e));return[...t.filter(e=>e.running),...t.filter(e=>!e.running&&Ma(e)<86400),...t.filter(e=>!e.running&&Ma(e)>=86400)]}pick(e){this.close(),e!==this.current&&n(this,`ca-select-run`,{run:e})}close(){this.dispatchEvent(new Event(`close`))}onKey(e,t){if(e.key===`Escape`)return this.close();if(e.key===`ArrowDown`)this.kb=Math.min(t.length-1,this.kb+1);else if(e.key===`ArrowUp`)this.kb=Math.max(0,this.kb-1);else if(e.key===`Enter`){let e=t[Math.max(0,this.kb)];e&&this.pick(e.run);return}else return;e.preventDefault(),this.updateComplete.then(()=>this.renderRoot.querySelector(`.item.kb`)?.scrollIntoView({block:`nearest`}))}render(){let e=this.visible(),t=[[w(`Running`),e.filter(e=>e.running)],[w(`Last 24 hours`),e.filter(e=>!e.running&&Ma(e)<86400)],[w(`Older`),e.filter(e=>!e.running&&Ma(e)>=86400)]],n=0;return A`<div class="search">
        <input placeholder=${w(`Search runs`)} aria-label=${w(`Search runs`)} autocomplete="off" .value=${this.q}
          @input=${e=>{this.q=e.target.value,this.kb=0}}
          @keydown=${t=>this.onKey(t,e)} />
        <div class="keys meta" aria-hidden="true"><span class="kbd">↑</span><span class="kbd">↓</span> <span class="kbd">Enter</span> <span class="kbd">Esc</span></div>
      </div>
      <div class="list" role="listbox">
        ${e.length?t.map(([e,t])=>t.length?A`<div class="group">${e} <span class="n">${t.length}</span></div>
                    ${t.map(e=>this.item(e,n++))}`:j):A`<div class="blank"><span>${w(`No runs match`)}</span></div>`}
      </div>`}counts(e){let t=e.tasks,n=[w(S`${t.done} of ${t.total} tasks done`)];t.failed&&n.push(K(`failed`,t.failed)),t.not_started&&n.push(K(`not_started`,t.not_started)),t.running&&n.push(K(`running`,t.running)),t.waiting&&n.push(K(`waiting`,t.waiting));let r=ja(e);r!=null&&n.push(w(S`took ${N(r)}`)),e.cost_usd!==null&&e.cost_usd!==void 0&&n.push(on(e.cost_usd));let i=Oa(e.quota??[]);return i&&n.push(i),F(...n)}item(e,t){let n=e.running?`live`:e.tasks.failed||e.tasks.not_started?`warn`:`ok`;return A`<div class=${`item${e.run===this.current?` cur`:``}${t===this.kb?` kb`:``}`} role="option" aria-selected=${e.run===this.current} @click=${()=>this.pick(e.run)}>
      <span class="dot ${n}" aria-hidden="true"></span><span class="nm">${e.run}</span>
      <span class="when" title=${P(e.last_ts,!0)}>${e.running?w(`running`):nn(e.last_ts)}</span>
      <span class="sub">
        ${e.run_group&&e.run_group!==e.run?A`<span>${w(S`Run group ${e.run_group}`)}</span>`:j}
        <span title=${ka(e.quota??[])}>${this.counts(e)}</span>
      </span>
    </div>`}};U([V({attribute:!1})],Na.prototype,`runs`,void 0),U([V()],Na.prototype,`current`,void 0),U([V({type:Boolean,reflect:!0})],Na.prototype,`open`,void 0),U([H()],Na.prototype,`q`,void 0),U([H()],Na.prototype,`kb`,void 0),U([kn(`input`)],Na.prototype,`input`,void 0),Na=U([B(`ca-run-picker`),D()],Na);var{I:Pa}=zt,Fa=e=>e,Ia=()=>document.createComment(``),La=(e,t,n)=>{let r=e._$AA.parentNode,i=t===void 0?e._$AB:t._$AA;if(n===void 0)n=new Pa(r.insertBefore(Ia(),i),r.insertBefore(Ia(),i),e,e.options);else{let t=n._$AB.nextSibling,a=n._$AM,o=a!==e;if(o){let t;n._$AQ?.(e),n._$AM=e,n._$AP!==void 0&&(t=e._$AU)!==a._$AU&&n._$AP(t)}if(t!==i||o){let e=n._$AA;for(;e!==t;){let t=Fa(e).nextSibling;Fa(r).insertBefore(e,i),e=t}}}return n},Ra=(e,t,n=e)=>(e._$AI(t,n),e),za={},Ba=(e,t=za)=>e._$AH=t,Va=e=>e._$AH,Ha=e=>{e._$AR(),e._$AA.remove()},Ua=(e,t,n)=>{let r=new Map;for(let i=t;i<=n;i++)r.set(e[i],i);return r},X=Vn(class extends Hn{constructor(e){if(super(e),e.type!==Bn.CHILD)throw Error(`repeat() can only be used in text expressions`)}dt(e,t,n){let r;n===void 0?n=t:t!==void 0&&(r=t);let i=[],a=[],o=0;for(let t of e)i[o]=r?r(t,o):o,a[o]=n(t,o),o++;return{values:a,keys:i}}render(e,t,n){return this.dt(e,t,n).values}update(e,[t,n,r]){let i=Va(e),{values:a,keys:o}=this.dt(t,n,r);if(!Array.isArray(i))return this.ut=o,a;let s=this.ut??=[],c=[],l,u,d=0,f=i.length-1,p=0,m=a.length-1;for(;d<=f&&p<=m;)if(i[d]===null)d++;else if(i[f]===null)f--;else if(s[d]===o[p])c[p]=Ra(i[d],a[p]),d++,p++;else if(s[f]===o[m])c[m]=Ra(i[f],a[m]),f--,m--;else if(s[d]===o[m])c[m]=Ra(i[d],a[m]),La(e,c[m+1],i[d]),d++,m--;else if(s[f]===o[p])c[p]=Ra(i[f],a[p]),La(e,i[d],i[f]),f--,p++;else if(l===void 0&&(l=Ua(o,p,m),u=Ua(s,d,f)),l.has(s[d])){if(l.has(s[f])){let t=u.get(o[p]),n=t===void 0?null:i[t];if(n===null){let t=La(e,i[d]);Ra(t,a[p]),c[p]=t}else c[p]=Ra(n,a[p]),La(e,i[d],n),i[t]=null;p++}else Ha(i[f]),f--}else Ha(i[d]),d++;for(;p<=m;){let t=La(e,c[m+1]);Ra(t,a[p]),c[p++]=t}for(;d<=f;){let e=i[d++];e!==null&&Ha(e)}return this.ut=o,Ba(e,c),Tt}}),Wa={ok:`✓`,err:`✕`,warn:``,live:`●`,llm:`✦`},Ga=5200,Ka=class extends M{constructor(...e){super(...e),this.toasts=[],this.next=0}static{this.styles=[z,k`
      :host { position: fixed; right: 18px; bottom: 18px; display: flex; flex-direction: column; gap: 8px; z-index: 60; pointer-events: none; }
      .toast { pointer-events: auto; min-width: 240px; max-width: 380px; padding: 10px 14px; border-radius: 11px;
        background: var(--panel2); border: 1px solid var(--line2); box-shadow: 0 18px 40px rgba(0, 0, 0, 0.55);
        display: flex; gap: 10px; align-items: flex-start; animation: toast-in 0.35s var(--ease) both; }
      .toast.out { animation: toast-out 0.35s var(--ease) both; }
      .ti { font-size: 16px; line-height: 1.2; }
      b { display: block; font-size: 12.5px; }
      span.sub { font-size: 11.5px; color: var(--mut); }
      .ok { border-color: rgba(52, 211, 153, 0.45); }
      .err { border-color: rgba(248, 113, 113, 0.45); }
      .warn { border-color: rgba(251, 191, 36, 0.45); }
      .live { border-color: rgba(34, 211, 238, 0.45); }
    `]}show(e,t,n=``){let r={id:this.next++,kind:e,title:t,sub:n,out:!1};this.toasts=[...this.toasts,r].slice(-4),setTimeout(()=>{this.toasts=this.toasts.map(e=>e.id===r.id?{...e,out:!0}:e),setTimeout(()=>this.toasts=this.toasts.filter(e=>e.id!==r.id),400)},Ga)}render(){return A`<div aria-live="polite" style="display:contents">
      ${X(this.toasts,e=>e.id,e=>A`<div class="toast ${e.kind} ${e.out?`out`:``}">
          <span class="ti" aria-hidden="true">${Wa[e.kind]}</span>
          <div><b>${e.title}</b>${e.sub?A`<span class="sub">${e.sub}</span>`:j}</div>
        </div>`)}
    </div>`}};U([H()],Ka.prototype,`toasts`,void 0),Ka=U([B(`ca-toasts`)],Ka);function qa(e){switch(e){case`valid`:return w(`passed`);case`invalid`:return w(`failed checks`);case`refused`:return w(`not written (task not started)`);case`failed`:return w(`not written (task failed)`);case`running`:return w(`not written yet (task running)`);case`pending`:return w(`not written yet (task waiting)`)}}function Ja(e){switch(e){case`refused`:return w(`The task did not start because an input was missing or failed checks`);case`valid`:return w(`The file passed its checks`);case`invalid`:return w(`The file failed its checks`);case`failed`:return w(`The task failed before it wrote a file that passes its checks`);case`running`:return w(`The task is running`);case`pending`:return w(`The task is waiting`)}}var Ya=()=>w(`Correction: another round in the same agent session after the output failed checks`);function Xa(e,t){let n=(e??1)-1;return n<1?``:w(t?n===1?`after 1 correction`:S`after ${n} corrections`:n===1?`1 correction`:S`${n} corrections`)}var Za=(e,t,n=``)=>A`<span class="fk ${e?`ok`:`bad`}" title=${n||j}><span aria-hidden="true">${e?`✓`:`✕`}</span> ${t}</span>`;function Qa(e){let t=!!e.file.exists,n=t?w(`found`):e.required?w(`missing (required)`):w(`missing (optional)`);return A`<span class="ct-chip ${t?`valid`:e.required?`invalid`:`pending`}">${n}</span>`}var $a=[`valid`,`invalid`,`refused`,`failed`,`running`,`pending`];Object.defineProperties({},Object.fromEntries($a.map(e=>[e,{enumerable:!0,get:()=>qa(e)}]))),Object.defineProperties({},Object.fromEntries($a.map(e=>[e,{enumerable:!0,get:()=>Ja(e)}])));var eo=e=>e===`invalid`?`invalid_output`:e===`refused`?`invalid_input`:`error`;function to(e,t){return e.startsWith(`list[`)||e===`array`?Array.isArray(t):e===`string`?typeof t==`string`:e===`integer`?Number.isInteger(t):e===`number`?typeof t==`number`:e===`boolean`?typeof t==`boolean`:e!==`object`||typeof t==`object`&&!!t&&!Array.isArray(t)}var no=(e,t)=>e.length>t?`${e.slice(0,t)}…`:e;function ro(e){if(e===void 0)return A`<span class="jdim">—</span>`;if(typeof e==`string`)return A`<span class="js" title=${e}>"${no(e,90)}"</span>`;if(Array.isArray(e)){let t=e.slice(0,3).map(e=>typeof e==`string`?`"${no(e,28)}"`:JSON.stringify(e)).join(`, `);return A`<span class="jn">${e.length===1?w(`1 item`):w(S`${e.length} items`)}</span>
      <span class="jdim">${t}${e.length>3?`, …`:``}</span>`}return typeof e==`object`&&e?A`<span class="jn">${w(`object`)}</span> <span class="jdim">${Object.keys(e).slice(0,4).join(`, `)}</span>`:A`<span class="jn">${JSON.stringify(e)}</span>`}function io(e){let t=e.content;return typeof t==`object`&&t?A`<ca-json-tree .value=${t}></ca-json-tree>`:A`<pre class="jtree">${typeof t==`string`?t:w(`Not JSON`)}</pre>`}var ao=e=>/^RootModel\[(.+)\]$/.exec(e)?.[1]??null;function oo(e){let t=e.file,n=t.content;if(!e.fields.length&&(e.schema_name===`text`||ao(e.schema_name)!==null))return t.exists?A`<details class="ct-raw">
          <summary>${so(t)}</summary>
          ${io(t)}
        </details>`:A``;let r=t.exists&&typeof n==`object`&&n&&!Array.isArray(n)?n:null,i=e.fields.map(e=>{let t=A`<span class="fk none">${w(`no file`)}</span>`,n;if(r){let i=e.name in r;n=i?r[e.name]:void 0,t=i?to(e.type,n)?Za(!0,w(`passed`)):Za(!1,w(`wrong type`),w(S`Expected ${e.type}`)):e.required?Za(!1,w(`missing`),w(`A required field that is not in the file`)):A`<span class="fk none">${w(`absent (optional)`)}</span>`}return A`<tr>
      <td class="jmono">${e.name}</td>
      <td class="jmono jdim">${e.type}${e.required?j:A` <i>${w(`optional`)}</i>`}</td>
      <td>${ro(n)}</td>
      <td>${t}</td>
    </tr>`}),a=r?Object.keys(r).filter(t=>!e.fields.some(e=>e.name===t)):[];return A`<table class="ct-check">
      <tr><th>${w(`Field`)}</th><th>${w(`Expected`)}</th><th>${w(`In the file`)}</th><th>${w(`Check`)}</th></tr>
      ${i}
      ${a.map(e=>A`<tr>
          <td class="jmono">${e}</td><td class="jdim">${w(`not in the schema`)}</td><td>${ro(r?.[e])}</td>
          <td><span class="fk warn" title=${w(`Not in the schema`)}>${w(`extra field`)}</span></td>
        </tr>`)}
    </table>
    ${t.exists?r?j:A`<div class="meta note">${w(`Not a JSON object`)}</div>`:A`<div class="meta note">${e.status===`running`||e.status===`pending`||!e.status?w(`Not written yet`):w(`Not written`)}</div>`}
    ${t.exists?A`<details class="ct-raw">
          <summary>${so(t)}</summary>
          ${io(t)}
        </details>`:j}`}var so=e=>F(w(`Whole file`),`${e.size??0} B`,e.mtime?w(S`written ${P(e.mtime,!0)}`):``,e.truncated?w(`truncated`):``);function co(e){let t=ao(e.schema_name),n=e.schema_name===`text`||t===`str`?w(`text`):t??e.schema_name;return A`<b class="jmono" title=${e.schema_ref||e.schema_name}>${n}</b>`}function lo(e){let t=e.schema_ref||e.schema_name;if(e.schema_name===`text`)return w(`text file`);let n=ao(e.schema_name);return n===`str`?A`<span title=${t}>${w(`text (JSON string)`)}</span>`:n?A`<span title=${t}>${w(S`JSON value of type ${n}`)}</span>`:w(A`JSON object, schema ${co(e)}`)}function uo(e){let t=e.validators??[];if(!t.length)return null;let n=(e.errors??[]).join(`
`),r=t=>e.status===`valid`?Za(!0,w(`passed`)):n.includes(t)?Za(!1,w(`failed checks`)):j;return A`${t.map((e,t)=>A`${t?`, `:``}<span class="jmono">${e}</span> ${r(e)}`)}`}function fo(e,t,n){let r=e.errors??[],i=di(`invalid input: ${r.map(e=>e.replace(/^invalid input:\s*/,``)).join(`; `)}`)[0];if(!i)return r[0]?rn(J(r[0],t)):w(`An input was missing or failed checks`);let a=n?.(i.path);return rn(fi(J(i.path,t),i.problem,a))}function po(e,t){let n=lo(e),r=uo(e);return A`<dl class="conds">
    ${(t===`output`?[[w(`Format`),n],...r?[[w(`Other checks`),r,w(`Checks beyond the schema (validators)`)]]:[],[w(`Must be written during the task`),e.fresh?w(`yes`):w(`no`),e.fresh?w(`A file from before the task does not count`):w(`A file from before the task counts`)]]:[[w(`Format`),n],...r?[[w(`Other checks`),r,w(`Checks beyond the schema (validators)`)]]:[],[w(`Check time`),w(`when the task starts`)],[w(`Required`),e.required?w(`yes`):w(`no`)]]).map(([e,t,n])=>A`<dt>${e}</dt><dd title=${n??``}>${t}</dd>`)}
  </dl>`}function mo(e,t,n=``,r={}){let i=A`<div class="io-hd">${t===`output`?A`<span class="ct-chip ${e.status??``}" title=${e.status?Ja(e.status):``}>${e.status?qa(e.status):`—`}</span>${(e.rounds??0)>1?A` <span class="meta" title=${Ya()}>${Xa(e.rounds,e.status===`valid`)}</span>`:j}`:Qa(e)}<span class="jmono ct-path" title=${e.path}>${J(e.path,n)}</span></div>`;if(t===`output`&&e.status===`refused`)return A`<div class="io-card one">${i}<div class="meta">${fo(e,n,r.producerOf)}</div></div>`;if(t===`output`&&e.status===`failed`&&!e.file.exists)return A`<div class="io-card one">${i}</div>`;let a=e.errors??[];return A`<div class="io-card">
    ${i}
    ${po(e,t)}
    ${oo(e)}
    ${a.length?A`<h4>${w(`Errors`)}</h4><pre class="ct-err">${a.map(e=>J(e,n)).join(`
`)}</pre>`:j}
  </div>`}var ho=k`
  .ct-lead { margin: 2px 0 8px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 6px; }
  .conds { display: grid; grid-template-columns: max-content 1fr; gap: 2px 14px; margin: 2px 0 10px; font-size: 12px; }
  .conds dt { color: var(--mut); }
  .conds dd { margin: 0; color: var(--fg2); }
  /* sized to its content, so the check mark sits next to the value it judges; a long value wraps */
  .ct-check { width: auto; max-width: 100%; border-collapse: collapse; }
  .ct-check th { text-align: left; font-size: 11.5px; color: var(--mut);
    font-weight: 600; padding: 4px 20px 4px 0; border-bottom: 1px solid var(--line); }
  .ct-check td { padding: 5px 20px 5px 0; border: 0; border-bottom: 1px solid var(--line); vertical-align: baseline; font-size: 12.5px; }
  .ct-check th:last-child, .ct-check td:last-child { padding-right: 0; }
  .ct-check td:nth-child(3) { overflow-wrap: anywhere; }
  .ct-check tr:last-child td { border-bottom: 0; }
  .ct-check td:first-child { white-space: nowrap; font-weight: 600; }
  .ct-check td:last-child { white-space: nowrap; }
  .ct-check i { font-style: normal; color: var(--mut); font-size: 11px; margin-left: 4px; }
  .fk { font-size: 12px; }
  .fk.ok { color: var(--ok); }
  .fk.bad { color: var(--err); font-weight: 600; }
  .fk.warn { color: var(--warn); }
  .fk.none { color: var(--mut); }
  .js { color: var(--ok); }
  .jn { color: var(--warn); }
  .note { margin-top: 6px; }
  .ct-raw { margin-top: 8px; }
  .ct-raw > summary { cursor: pointer; color: var(--mut); font-size: 12px; }
  .ct-err { color: var(--err); white-space: pre-wrap; }
  .ct-fields { border-collapse: collapse; width: 100%; }
  .ct-fields td { padding: 2px 10px 2px 0; border: 0; font-size: 12px; }
  .ct-in { display: flex; align-items: center; gap: 10px; padding: 5px 4px; border-top: 1px solid var(--line); }
  h4 { margin: 8px 0 6px; font-size: 12px; color: var(--fg2); font-weight: 600; }
  .io-card { border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; background: var(--raise); }
  .io-hd { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
  .io-hd .ct-path { flex: 1; }
  .io-card.one .io-hd { margin-bottom: 2px; }
`,go=class extends M{constructor(...e){super(...e),this.procs=null}static{this.styles=[z,k`
      :host { display: block; }
      .ptree2 { font-family: var(--mono); font-size: 11.5px; max-height: 220px; overflow: auto; }
      .pt-n { display: flex; gap: 10px; align-items: center; padding: 3px 6px 3px calc(6px + var(--d) * 18px); border-radius: 6px; position: relative; }
      .pt-n:hover { background: rgba(255, 255, 255, 0.03); }
      .pt-n::before { content: ''; position: absolute; left: calc(var(--d) * 18px - 8px); top: 0; bottom: 50%; width: 8px;
        border-left: 1px solid #2a3a54; border-bottom: 1px solid #2a3a54; }
      .pt-n.root::before { display: none; }
      .pt-pid { color: var(--mut); min-width: 58px; }
      .pt-cmd { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; color: var(--fg2); }
      .pt-n.llm .pt-cmd { color: var(--llm); }
      .pt-age { color: var(--mut); }
    `]}render(){let e=this.procs?.tree[0];return e?A`<div class="ptree2">${this.node(e,0)}</div>`:A`<div class="meta">${w(`No running processes`)}</div>`}node(e,t){let n=e.full_cmd||e.cmd||``,r=(e.cmd||n).split(` `).slice(0,3).join(` `);return A`<div class="pt-n ${/\b(claude|omp)\b/.test(n)?`llm`:``} ${t?``:`root`}" style="--d:${t}" title=${n}>
        <span class="pt-pid">${e.pid}</span>
        <span class="pt-cmd">${e.key?A`<b>${I(e)}</b> `:j}${r.length>70?`${r.slice(0,70)}…`:r}</span>
        <ca-elapsed class="pt-age" .since=${In.at(`p:${e.pid}`,e.age_s)}></ca-elapsed>
      </div>
      ${(e.children??[]).map(e=>this.node(e,t+1))}`}};U([V({attribute:!1})],go.prototype,`procs`,void 0),go=U([B(`ca-proc-tree`),D()],go);function _o(e){return e?A`${e.split(` | `).map((e,t)=>A`${t?` | `:``}<span class="f">${e}</span>`)}`:j}function vo(e){let t=!1,n=!1,r=!1;for(let i of e){if(i.outcome!==`not_started`)continue;let e=i.attempts[i.attempts.length-1],a=e?.stop===`invalid_input`?di(e.reason):[];a.some(e=>e.problem===`missing`)&&(t=!0),a.some(e=>e.problem===`checks`)&&(n=!0),!a.length&&i.cause&&(r=!0)}return F(r?w(`Earlier task failed`):``,t?w(`Input missing`):``,n?w(`Input failed checks`):``)}var yo=()=>globalThis.matchMedia?.(`(prefers-reduced-motion: reduce)`).matches??!1,bo=class extends M{constructor(...e){super(...e),this.journal=[],this.plan={nodes:[],groups:[]},this.prev=new Map,this.changed=[]}static{this.styles=[z,k`
      :host { display: block; }
      .kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
      @media (max-width: 1150px) { .kpis { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
      @media (max-width: 700px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      .kpi { background: rgba(255, 255, 255, 0.02); border: 1px solid var(--line); border-radius: 11px; padding: 12px 14px; }
      .k { font-size: 12px; font-weight: 600; color: var(--mut); }
      .v { font-size: 28px; font-weight: 700; line-height: 1.15; margin-top: 6px; font-variant-numeric: tabular-nums; }
      .s { font-size: 11.5px; color: var(--mut); margin-top: 2px; }
      .a { font-size: 11.5px; margin-top: 4px; }
      .kpi.ok .v { color: var(--ok); }
      .kpi.warn .v { color: var(--warn); }
      .kpi.err .v { color: var(--err); }
      .kpi.llm .v { color: var(--llm); }
    `]}history(e){return()=>n(this,`ca-navigate`,{tab:`journal`,stop:e})}show(e,t,r){let i=e.length===1?e[0]:void 0,a=i?this.journal.find(e=>e.key===i):void 0;return i?{label:a?I(a):i,run:()=>n(this,`ca-open-task`,{key:i})}:{label:r,run:this.history(t)}}tiles(){let e=_a(this.journal),t=jr(this.journal,this.plan),n=Nr(t),r=F(K(`done`,n.done+n.recovered),n.failed?K(`failed`,n.failed):``,n.not_started?K(`not_started`,n.not_started):``);return[{id:`tasks`,cls:n.failed?`err`:``,label:w(`Tasks`),value:n.total,sub:r},{id:`attempts`,cls:``,label:w(`Attempts`),value:e.attempts,sub:F(e.launches===1?w(`1 agent session`):w(S`${e.launches} agent sessions`),e.python===1?w(`1 Python task attempt`):w(S`${e.python} Python task attempts`)),tip:w(`Attempts that ran, retries included (journal.jsonl)`)},...this.spendTiles(),{id:`bad`,cls:e.bad?`err`:`ok`,label:w(`Failed attempts`),value:e.bad,sub:e.bad?``:w(`All attempts passed`),...e.bad?{action:{label:w(`Failed attempts in history`),run:this.history(`bad`)}}:{}},{id:`notstarted`,cls:n.not_started?`warn`:``,label:w(`Not started`),value:n.not_started,sub:n.not_started?vo(t.values()):w(`All tasks started`),...n.not_started?{action:{label:w(`Not-started tasks in history`),run:this.history(`invalid_input`)}}:{}},{id:`wall`,cls:`llm`,label:w(`Agent session time`),value:N(e.launchWall),sub:w(S`Python tasks: ${N(e.pythonWall)}`),tip:w(`Sum over all agent sessions, including ones running at once`)},{id:`retry`,cls:e.retries?`warn`:``,label:w(`Retries`),value:e.retries,sub:e.retries?e.retriedTasks===1?w(`1 task retried`):w(S`${e.retriedTasks} tasks retried`):w(`No retries`),tip:w(`Attempts after a failed attempt, each in a new agent session (RetryingRunner)`),...e.retries?{action:this.show(e.retriedKeys,`retried`,w(`Retried tasks in history`))}:{}},{id:`ct`,cls:e.fixups?`warn`:``,label:w(`Corrections`),value:e.fixups,sub:e.fixups?e.fixupTasks===1?w(`1 task with corrections`):w(S`${e.fixupTasks} tasks with corrections`):w(`No corrections`),tip:w(`More rounds in the same agent session after the output failed checks (rounds)`),...e.fixups?{action:this.show(e.fixupKeys,`fixup`,w(`Attempts with corrections in history`))}:{}},{id:`fo`,cls:e.switches?`warn`:``,label:w(`Model switches`),value:e.switches,sub:e.switches?e.switchTasks===1?w(`1 task with model switches`):w(S`${e.switchTasks} tasks with model switches`):w(`No model switches`),tip:w(`To the next model after a failure such as a rate limit, an error or a timeout (Router hops)`)}]}spendTiles(){let e=Br(this.journal);if(!e)return[];let t=Ur(this.journal)[0];return[{id:`cost`,cls:`llm`,label:w(`Cost`),value:on(e.cost),sub:t&&t.share!==null?[w(S`Highest cost: ${t.kind}`),F(on(t.spend.cost),w(S`${Math.round(t.share*100)}% of the total`))]:``,tip:w(`Reported by the coding agent`)},{id:`tokens`,cls:``,label:w(`Tokens`),value:R(Rr(e)),sub:F(w(S`${R(e.input)} input`),w(S`${R(e.output)} output`),w(S`${R(e.cache_read+e.cache_creation)} cache`)),tip:F(w(S`${R(e.cache_read)} cache read`),w(S`${R(e.cache_creation)} cache write`),e.calls===1?w(`1 API call`):w(S`${e.calls} API calls`))}]}render(){let e=this.tiles();this.changed=[];for(let t of e)typeof t.value==`number`&&((this.prev.get(t.id)??0)!==t.value&&this.changed.push(t.id),this.prev.set(t.id,t.value));return A`<div class="kpis">${e.map(e=>this.tile(e))}</div>`}tile(e){return A`<div class="kpi ${e.cls}" data-id=${e.id} title=${e.tip??j}>
      <div class="k words">${e.label}</div>
      <div class="v">${typeof e.value==`number`?A`<ca-count .value=${e.value}></ca-count>`:e.value}</div>
      ${(typeof e.sub==`string`?[e.sub]:e.sub).map(e=>A`<div class="s words">${_o(e)}</div>`)}
      ${e.action?A`<div class="a words"><a class="lnk" href="#" @click=${t=>{t.preventDefault(),e.action?.run()}}>${e.action.label}</a></div>`:j}
    </div>`}updated(){if(!yo())for(let e of this.changed)this.renderRoot.querySelector(`.kpi[data-id="${e}"]`)?.animate([{transform:`scale(1)`},{transform:`scale(1.04)`,boxShadow:`0 0 0 1px var(--live)`,offset:.35},{transform:`scale(1)`}],{duration:700,easing:`cubic-bezier(.2,.8,.2,1)`})}};U([V({attribute:!1})],bo.prototype,`journal`,void 0),U([V({attribute:!1})],bo.prototype,`plan`,void 0),bo=U([B(`ca-kpis`),D()],bo);var xo=[`input`,`cache_read`,`cache_creation`,`output`],So=class extends M{constructor(...e){super(...e),this.journal=[],this.top=5}static{this.styles=[z,k`
      :host { display: block; }
      .kinds { display: grid; grid-template-columns: minmax(90px, max-content) minmax(0, 1fr) max-content max-content; gap: 8px 14px; align-items: center; }
      .kind { font-family: var(--mono); font-size: 12px; color: var(--fg2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .bar { display: flex; height: 12px; border-radius: 4px; overflow: hidden; background: var(--track); }
      .bar i { display: block; height: 100%; }
      .num { font-variant-numeric: tabular-nums; text-align: right; font-size: 12px; white-space: nowrap; }
      .share { color: var(--mut); min-width: 3.5em; }
      .p-input { background: var(--tok-input); }
      .p-cache_read { background: var(--tok-cache-read); }
      .p-cache_creation { background: var(--tok-cache-write); }
      .p-output { background: var(--tok-output); }
      .legend { margin-top: 10px; }
      h4 { margin: 16px 0 6px; font-size: 12px; color: var(--fg2); font-weight: 600; }
      .top { display: grid; grid-template-columns: minmax(160px, max-content) 64px 64px 40px; column-gap: 24px; row-gap: 4px; align-items: baseline; }
      .top a { font-family: var(--mono); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    `]}partLabel(e){switch(e){case`input`:return w(`input`);case`cache_read`:return w(`cache read`);case`cache_creation`:return w(`cache write`);case`output`:return w(`output`)}}bar(e,t){let n=Rr(e),r=t?100*n/t:0;return A`<div class="bar" title=${F(...xo.map(t=>`${this.partLabel(t)} ${R(e[t])}`))} style="width:${Math.max(r,.5).toFixed(2)}%">
      ${xo.map(t=>e[t]&&n?A`<i class="p-${t}" style="width:${(100*e[t]/n).toFixed(2)}%"></i>`:j)}
    </div>`}render(){if(!Br(this.journal))return A`<div class="meta">${w(`No tokens reported`)}</div>`;let e=Ur(this.journal),t=Math.max(1,...e.map(e=>Rr(e.spend))),r=Hr(this.journal).slice(0,this.top);return A`<div class="kinds">
        ${X(e,e=>e.id,e=>A`<span class="kind" title=${e.id}>${e.id}</span>${this.bar(e.spend,t)}
            <span class="num">${F(R(Rr(e.spend)),on(e.spend.cost))}</span>
            <span class="num share">${e.share===null?``:`${Math.round(e.share*100)}%`}</span>`)}
      </div>
      <div class="legend">${xo.map(e=>A`<span><i class="p-${e}"></i>${this.partLabel(e)}</span>`)}</div>
      <h4>${w(`Most expensive tasks`)}</h4>
      <div class="top">
        ${r.map(e=>A`<a class="lnk" href="#" title=${e.id} @click=${t=>{t.preventDefault(),n(this,`ca-open-task`,{key:e.id})}}>${I(e)}</a>
            <span class="num">${R(Rr(e.spend))}</span>
            <span class="num">${on(e.spend.cost)}</span>
            <span class="num share">${e.share===null?``:w(S`${Math.round(e.share*100)}%`)}</span>`)}
      </div>`}};U([V({attribute:!1})],So.prototype,`journal`,void 0),U([V({type:Number})],So.prototype,`top`,void 0),So=U([B(`ca-spend-breakdown`),D()],So);var Co=class extends M{static{this.styles=[z,k`
      :host { display: block; }
      .rows { display: grid; grid-template-columns: max-content minmax(0, 1fr) max-content max-content; gap: 10px 14px; align-items: center; }
      .name { font-size: 12px; color: var(--fg2); white-space: nowrap; }
      .bar { position: relative; height: 12px; border-radius: 4px; background: var(--track); overflow: hidden; }
      .bar i { position: absolute; top: 0; bottom: 0; }
      .bar .before { left: 0; background: var(--muted); opacity: 0.55; }
      .bar .during { background: var(--live); }
      .bar.hot .during { background: var(--warn); }
      .bar.full .during { background: var(--err); }
      .val { font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
      .val b { color: var(--fg); }
      .reset { font-size: 11.5px; color: var(--mut); white-space: nowrap; }
      .status { margin-top: 8px; }
      .acct { padding: 10px 0; border-top: 1px solid var(--line); }
      .acct:first-child { border-top: 0; padding-top: 0; }
      .acct-h { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; font-size: 12px; }
      .acct-h i { font-style: normal; color: var(--mut); font-size: 11px; }
      .acct-h b { font-family: var(--mono); color: var(--fg); font-weight: 600; }
    `]}constructor(){super(),this.journal=[],new Fn(this)}row(e,t,n,r){let i=n[`${e}_pct`],a=r[`${e}_pct`];if(i==null&&a==null)return j;let o=Math.max(0,Math.min(100,i??a??0)),s=Math.max(o,Math.min(100,a??o)),c=r[`${e}_resets_at`];return A`<span class="name">${t}</span>
      <span class="bar ${s>=100?`full`:s>=80?`hot`:``}" title=${`${Sa(i)} → ${Sa(a)}`}>
        <i class="before" style="width:${o}%"></i>
        <i class="during" style="left:${o}%;width:${s-o}%"></i>
      </span>
      <span class="val">${Sa(i)} → <b>${Sa(a)}</b></span>
      <span class="reset" title=${c?P(c,!0):``}>${wa(c)}</span>`}render(){let e=qr(this.journal);return e.length?A`${e.map(e=>{let t=Ca(e.last.status);return A`<div class="acct">
        <div class="acct-h"><i>${w(`Identity`)}</i><b>${si(e.credential)||`—`}</b>${t?A`<span class="pill p-timeout" title=${e.last.status??``}>${t}</span>`:j}</div>
        <div class="rows">
          ${this.row(`seven_day`,w(`Weekly usage`),e.first,e.last)} ${this.row(`five_hour`,w(`5-hour usage`),e.first,e.last)}
        </div>
      </div>`})}`:j}};U([V({attribute:!1})],Co.prototype,`journal`,void 0),Co=U([B(`ca-quota`),D()],Co);var wo=[`done`,`running`,`pending`,`failed`,`blocked`,`skipped`],To=640,Eo=.7,Do=360,Oo=2.5,ko=4,Ao=24,jo=150,Mo=30,No=8,Po=e=>[...e.units,...e.single];function Fo(e,t){let n=Po(e),r=e.units.length?sa(t):sa(n.length);return{cols:Math.min(r.cols,Math.max(1,n.length)),size:r.size,gap:r.size>=10?4:2}}var Z=class extends M{constructor(...e){super(...e),this.plan={nodes:[],groups:[]},this.journal=[],this.run=``,this.live=!1,this.layer=``,this.unit=``,this.hover=null,this.asTable=!1,this.down=!1,this.lay=null,this.view={k:1,x:0,y:0},this.frameH=0,this.sort=`order`,this.scrollRow=0,this.auto=[],this.segments=[],this.graph={path:[],nodes:[],layers:[],boxes:[],edges:[],stubs:[],units:[],slots:{},routes:[],order:{layers:[],boxes:{}}},this.matrix=null,this.orders=new Map,this.byKey=new Map,this.waiters=new Map,this.active=new Map,this.cell=null,this.refocus=!1,this.cameFrom=``,this.layKey=``,this.fitK=1,this.moved=!1,this.pan=null,this.swallowClick=!1,this.onEscape=e=>{if(e.key!==`Escape`||e.defaultPrevented)return;let t=ra(this.segments,this.auto);t&&(e.preventDefault(),this.refocus=!0,this.cameFrom=this.segments[this.segments.length-1]??``,this.go(t))},this.onWheel=e=>{if(this.asTable||this.matrix||!(e.ctrlKey||e.metaKey))return;let t=this.renderRoot.querySelector(`.frame`);if(!t)return;e.preventDefault();let n=t.getBoundingClientRect();this.zoomBy(Math.exp(-e.deltaY*.0015),e.clientX-n.left,e.clientY-n.top)},this.onClickCapture=e=>{this.swallowClick&&(this.swallowClick=!1,e.stopPropagation(),e.preventDefault())}}static{this.styles=[z,k`
      :host { display: block; }

      .frame { position: relative; overflow: hidden; border-radius: 8px; background: rgba(0, 0, 0, 0.12); cursor: grab; touch-action: none; }
      .frame.drag { cursor: grabbing; }
      .stage { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
      .frame.down { touch-action: pan-y pinch-zoom; }
      .tools { display: flex; gap: 4px; margin-left: auto; }
      .tools button { all: unset; cursor: pointer; min-width: 22px; height: 22px; padding: 0 7px; box-sizing: border-box; text-align: center;
        font-size: 11.5px; line-height: 22px; color: var(--fg2); border-radius: 6px; border: 1px solid var(--line); }
      .tools button:hover:not(:disabled) { color: var(--fg); border-color: var(--line2); }
      .tools button:focus-visible { outline: 2px solid var(--live); outline-offset: 1px; }
      .tools button:disabled { cursor: default; opacity: 0.4; }

      .dag { position: relative; }
      .dag.unplaced { visibility: hidden; }
      .dag > *, .box > .in > * { position: absolute; }
      .edges { left: 0; top: 0; pointer-events: none; overflow: visible; z-index: 0; }
      .edges path { fill: none; stroke: var(--line2); stroke-width: 1.5; }
      .edges path.created { stroke-dasharray: 5 4; }
      .unset { visibility: hidden; }

      .stub { z-index: 1; font-family: var(--mono); font-size: 11.5px; color: var(--mut); padding: 3px 9px;
        border-radius: 999px; border: 1px solid var(--line); background: var(--card); white-space: nowrap; }

      .box { z-index: 1; box-sizing: border-box; border-radius: 14px; border: 1px solid var(--line2); background: rgba(148, 163, 184, 0.045); }
      .box .box { background: rgba(148, 163, 184, 0.06); }
      .box > .in { position: absolute; inset: 0; pointer-events: none; }
      .box > .in > * { pointer-events: auto; }
      .box > .hd { position: absolute; left: 11px; top: 6px; display: flex; flex-direction: column; align-items: flex-start; gap: 1px;
        white-space: nowrap; justify-content: flex-start; }
      .box > .hd .line { display: flex; align-items: baseline; gap: 8px; }
      .box > .hd .spread { font-size: 11px; color: var(--fg2); font-variant-numeric: tabular-nums; }
      /* The next-pass mark sits on the box's edge, where no edge crosses it: below its first layer
         (left to right), or beside its last (top to bottom). */
      .ret { position: absolute; left: 14px; bottom: -8px; display: grid; place-items: center; width: 22px; height: 15px;
        border-radius: 8px; background: var(--card); border: 1px solid var(--line2); color: var(--fg2); }
      .down .ret { left: auto; right: -12px; bottom: 14px; transform: rotate(90deg); }
      .ret svg { display: block; }

      .node { z-index: 1; width: max-content; min-width: 120px; box-sizing: border-box;
        display: flex; flex-direction: column; gap: 7px; padding: 8px 10px 9px;
        border-radius: 10px; border: 1px solid var(--line); background: var(--card); transition: border-color 0.3s, box-shadow 0.3s; }
      .node.flow { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--line2); }
      .node.done { border-color: rgba(52, 211, 153, 0.32); }
      .node.cur { border-color: var(--live); }
      .node.flow.cur { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--live), 0 0 14px rgba(34, 211, 238, 0.12); }
      .node:not(.flow).cur { box-shadow: 0 0 14px rgba(34, 211, 238, 0.12); }
      .node.fail { border-color: rgba(248, 113, 113, 0.55); }
      .node:focus-within { border-color: var(--fg2); }
      .hd { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
      .name { all: unset; cursor: pointer; font-family: var(--mono); font-weight: 600; font-size: 12.5px; color: var(--fg);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; }
      .name:hover { text-decoration: underline; }
      .name:focus-visible { outline: 2px solid var(--live); outline-offset: 2px; border-radius: 3px; }
      .count { font-size: 11px; color: var(--mut); font-variant-numeric: tabular-nums; white-space: nowrap; }
      .ex { display: flex; flex-wrap: wrap; gap: 0 10px; font-size: 11px; line-height: 1.5;
        max-width: max(98px, calc(var(--cols) * var(--m) + (var(--cols) - 1) * var(--g))); }
      .ex .err { color: var(--err); }
      .ex .warn { color: var(--warn); }
      .ex .live { color: var(--live); }
      .ex .mut { color: var(--mut); }

      .marks { display: grid; grid-template-columns: repeat(var(--cols), var(--m)); gap: var(--g); }
      .slot { width: var(--m); height: var(--m); }
      .mark { width: var(--m); height: var(--m); padding: 0; margin: 0; border: 0; border-radius: 50%; background: var(--ok); opacity: 0.9;
        cursor: pointer; position: relative; transition: opacity 0.2s, transform 0.15s, background 0.3s; }
      .mark.skipped { opacity: 0.4; }
      .mark.running { background: var(--live); opacity: 1; animation: breathe 1.4s ease-in-out infinite; }
      .mark.pending { background: transparent; box-shadow: inset 0 0 0 1.5px var(--line2); }
      .mark.blocked { border-radius: 2px; background: repeating-linear-gradient(135deg, transparent 0 2px, rgba(251, 191, 36, 0.55) 2px 3px);
        box-shadow: inset 0 0 0 1.5px var(--warn); opacity: 1; }
      .mark.failed { border-radius: 2px; background: var(--err); opacity: 1; }
      .big .mark.failed::after { content: '✕'; position: absolute; inset: 0; display: grid; place-items: center; color: #fff;
        font-size: calc(var(--m) - 3px); line-height: 1; font-weight: 700; }
      /* A unit that ran more than 1 pass: its number in the mark; a small mark has a hole instead. */
      .mark[data-n]::after { content: ''; position: absolute; inset: 32%; border-radius: 50%; background: var(--card); }
      .big .mark[data-n]::after { content: attr(data-n); inset: 0; display: grid; place-items: center; border-radius: 0; background: none;
        font: 700 max(7px, calc(var(--m) - 4px)) / 1 var(--sans); color: #04241a; letter-spacing: -0.5px; }
      .big .mark.failed[data-n]::after { color: #fff; }
      .big .mark.running[data-n]::after { color: #03222a; }
      .big .mark.pending[data-n]::after, .big .mark.blocked[data-n]::after, .big .mark.skipped[data-n]::after { color: var(--fg); }
      .mark:hover, .mark:focus-visible { transform: scale(1.4); outline: 2px solid var(--fg); outline-offset: 1px; z-index: 2; }
      .hl .mark:not(.on) { opacity: 0.16; }
      .hl .mark.on { transform: scale(1.2); }
      .mx.hl .mark:not(.on) { opacity: 0.4; }
      @media (prefers-reduced-motion: reduce) {
        .mark, .node { transition: none; }
        .mark.running { animation: none; background: linear-gradient(90deg, var(--live) 50%, transparent 50%); box-shadow: inset 0 0 0 1.5px var(--live); }
      }

      .sbar { display: flex; width: 220px; height: 10px; border-radius: 3px; overflow: hidden; background: var(--track); gap: 1px; }
      .sbar i { display: block; min-width: 2px; height: 100%; }
      .sbar .done { background: var(--ok); opacity: 0.85; }
      .sbar .running { background: var(--live); }
      .sbar .pending { background: var(--line2); }
      .sbar .failed { background: var(--err); }
      .sbar .blocked { background: repeating-linear-gradient(135deg, var(--warn-a) 0 2px, rgba(251, 191, 36, 0.6) 2px 3px); }
      .sbar .skipped { background: var(--ok); opacity: 0.35; }
      .fails { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; max-width: 220px; font-size: 11px; color: var(--mut); }
      .fails .taskchip { color: var(--err); border-color: rgba(248, 113, 113, 0.45); }
      .fails .taskchip:focus-visible { outline: 2px solid var(--fg); outline-offset: 1px; }
      .hl .fails .taskchip:not(.on) { opacity: 0.4; }

      .mxbar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-bottom: 8px; font-size: 12px; color: var(--fg2); }
      .mxbar label { display: inline-flex; align-items: center; gap: 6px; margin-left: auto; color: var(--mut); font-size: 11.5px; }
      .mxbar select { font: inherit; font-size: 11.5px; color: var(--fg); background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 2px 6px; }
      .mxbar select:focus-visible { outline: 2px solid var(--live); outline-offset: 1px; }
      .mx { overflow: auto; width: fit-content; max-width: 100%; max-height: max(${Do}px, ${Eo*100}vh); border-radius: 8px; background: rgba(0, 0, 0, 0.12); }
      table.matrix { border-collapse: separate; border-spacing: 0; font-size: 11px; width: max-content; }
      .matrix th, .matrix td { padding: 0 6px; height: ${Ao}px; border-bottom: 1px solid var(--line); white-space: nowrap; }
      .matrix thead th { position: sticky; z-index: 2; background: var(--panel2); color: var(--mut); font-weight: 500; text-align: center; height: 22px; }
      .matrix thead th.nh { font-family: var(--mono); color: var(--fg2); font-weight: 600; max-width: 110px; overflow: hidden; text-overflow: ellipsis; }
      .matrix thead th.pass { color: var(--fg2); }
      .matrix thead th.loop { font-family: var(--mono); }
      .matrix .uh, .matrix tbody th { position: sticky; left: 0; z-index: 1; background: var(--panel); text-align: left; }
      .matrix thead .uh { z-index: 3; }
      .matrix thead .uh, .matrix thead .pn { background: var(--panel2); }
      .matrix tbody th { font-family: var(--mono); font-weight: 600; color: var(--fg); max-width: 220px; overflow: hidden; text-overflow: ellipsis; }
      .matrix tbody th.none { font-family: var(--sans); font-weight: 500; color: var(--mut); }
      .matrix .pn { text-align: right; color: var(--mut); font-variant-numeric: tabular-nums; }
      .matrix .pn.many { color: var(--fg); font-weight: 600; }
      .matrix td.c { text-align: center; --m: 12px; }
      .matrix td.c .mark { vertical-align: middle; }
      .matrix .g0 { border-left: 1px solid var(--line2); }
      .matrix .g1 { border-left: 1px dashed var(--line); }
      .matrix tbody tr:hover td, .matrix tbody tr:hover th { background-color: rgba(148, 163, 184, 0.06); }
      .matrix tbody tr.on td, .matrix tbody tr.on th { background-color: var(--live-a); }
      .matrix .gap td { padding: 0; border: 0; }

      .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-bottom: 8px; font-size: 12px; }
      .crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; list-style: none; margin: 0; padding: 0; }
      .crumbs li { display: inline-flex; align-items: center; gap: 4px; }
      .crumbs .sep { color: var(--mut); }
      .crumbs button { all: unset; cursor: pointer; color: var(--live); font-family: var(--mono); }
      .crumbs button:hover { text-decoration: underline; }
      .crumbs button:focus-visible { outline: 2px solid var(--live); outline-offset: 2px; border-radius: 3px; }
      .crumbs [aria-current] { font-family: var(--mono); color: var(--fg); font-weight: 600; }
      .pin { display: inline-flex; align-items: center; gap: 8px; color: var(--fg2); }
      .pin b { font-family: var(--mono); }

      .foot { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-top: 6px; }
      .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11px; color: var(--mut); }
      .legend > span { white-space: nowrap; }
      .legend span { display: inline-flex; align-items: center; gap: 6px; }
      .legend .mark { --m: 12px; cursor: default; animation: none; }
      .legend .mark:hover { transform: none; outline: none; }
      .legend svg path { stroke: var(--line2); stroke-width: 1.5; fill: none; }
      .keys { flex-basis: 100%; font-size: 11px; color: var(--mut); display: none; }
      .keys span { white-space: nowrap; }
      :host(:focus-within) .keys { display: block; }
      .switch { all: unset; cursor: pointer; font-size: 11.5px; color: var(--fg2); padding: 2px 8px; border-radius: 6px; border: 1px solid var(--line); }
      .switch:hover { color: var(--fg); border-color: var(--line2); }
      .switch:focus-visible { outline: 2px solid var(--live); outline-offset: 1px; }

      table.list { width: 100%; border-collapse: collapse; font-size: 12px; }
      .list th, .list td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); }
      .list td.n { text-align: right; font-variant-numeric: tabular-nums; }
      /* a header is as wide as its words: a narrow count column never breaks its header inside a word */
      .list thead th { color: var(--mut); font-weight: 500; font-size: 11px; white-space: nowrap; }
      .list tbody th { font-family: var(--mono); font-weight: 600; }
    `]}willUpdate(e){if(e.has(`run`)&&this.orders.clear(),e.has(`layer`)&&e.get(`layer`)!==void 0&&(this.moved=!1,this.active.clear(),this.cell=null,this.scrollRow=0,this.refocus=this.renderRoot instanceof ShadowRoot&&this.renderRoot.activeElement!==null),!e.has(`plan`)&&!e.has(`layer`)&&!e.has(`run`)&&!e.has(`down`))return;this.auto=ta(this.plan),this.segments=this.layer?this.layer.split(`/`):this.auto;let{path:t,loop:n}=na(this.segments),r=t.join(`/`);if(this.graph=ea(this.plan,t,this.orders.get(r),this.down),this.orders.set(r,this.graph.order),this.matrix=n?ia(this.plan,t,n,this.graph.order):null,e.has(`plan`)){this.byKey=new Map(this.plan.nodes.map(e=>[e.key,e])),this.waiters=new Map;for(let e of this.plan.nodes)for(let t of e.after??[])(this.waiters.get(t)??this.waiters.set(t,[]).get(t))?.push(e.key)}}disconnectedCallback(){super.disconnectedCallback(),this.removeEventListener(`wheel`,this.onWheel),this.removeEventListener(`click`,this.onClickCapture,{capture:!0}),this.removeEventListener(`keydown`,this.onEscape),this.resize?.disconnect(),this.resize=void 0}connectedCallback(){super.connectedCallback(),this.addEventListener(`wheel`,this.onWheel,{passive:!1}),this.addEventListener(`click`,this.onClickCapture,{capture:!0}),this.addEventListener(`keydown`,this.onEscape)}updated(){this.resize||(this.resize=new ResizeObserver(()=>this.fit()),this.resize.observe(this)),this.place(),(this.refocus||this.cameFrom)&&this.restoreFocus()}place(){let e=this.renderRoot.querySelector(`.dag`);if(!e)return;let t=new Map;for(let n of e.querySelectorAll(`[data-id]`))t.set(n.dataset.id??``,{w:n.offsetWidth,h:n.offsetHeight});let n=this.graph,r=JSON.stringify([n.path,n.slots,n.routes.map(e=>e.steps.map(e=>e.id)),this.down,[...t]]);if(r===this.layKey)return this.fit();this.layKey=r,this.lay=pa(n,t,this.down),this.updateComplete.then(()=>this.fit())}restoreFocus(){let e=this.cameFrom;this.refocus=!1,this.cameFrom=``;let t=this.renderRoot,n=null;if(e.startsWith(`loop:`))n=t.querySelector(`.box[data-box="${CSS.escape(e)}"] > .hd .name`);else if(e){let r=this.graph.nodes.find(t=>t.type===`flow`&&t.name===e);r&&(n=t.querySelector(`.node[data-id="${CSS.escape(r.id)}"] [tabindex="0"]`))}(n??t.querySelector(`.mark[tabindex="0"], .node .name, .crumbs button`))?.focus()}go(e,t=this.unit){let r=this.auto.join(`/`),i=e.join(`/`);n(this,`ca-navigate`,{layer:i===r?``:i,unit:t})}crumbs(){let e=this.segments,t=this.unit;if(!e.length&&!t)return j;let{path:r,loop:i}=na(e),a=[...r.map((e,t)=>({name:ji(e),tip:e,to:r.slice(0,t+1)})),...(i?i.slice(wi.length).split(`.`):[]).map((e,t,n)=>({name:ai(),tip:/^\d+$/.test(e)?w(S`Loop at ${this.where(e,this.matrix?.box.file||this.graph.boxes[0]?.file)}`):w(`Loop`),to:[...r,wi+n.slice(0,t+1).join(`.`)]}))];return A`<div class="bar">
      ${e.length?A`<nav aria-label=${w(`Pipeline layer`)}>
            <ol class="crumbs">
              <li><button type="button" @click=${()=>this.go([])}>${w(`Pipeline`)}</button></li>
              ${a.map((e,t)=>A`<li><span class="sep" aria-hidden="true">›</span>
                  ${t===a.length-1?A`<span aria-current="page" title=${e.tip}>${e.name}</span>`:A`<button type="button" title=${e.tip} @click=${()=>this.go(e.to)}>${e.name}</button>`}</li>`)}
            </ol>
          </nav>`:j}
      ${t?A`<span class="pin">${w(S`Unit: ${t}`)}
            <button type="button" class="switch" @click=${()=>n(this,`ca-navigate`,{unit:``})}>${w(`Clear highlight`)}</button></span>`:j}
    </div>`}fit(){let e=this.clientWidth,t=e>0&&e<To;t!==this.down&&(this.down=t);let n=this.lay;if(!n||this.matrix)return;let r=ha(n.w,n.h,e,t?1/0:Math.max(Do,Eo*window.innerHeight));this.fitK=r.k,this.moved||(r.h!==this.frameH&&(this.frameH=r.h),(r.k!==this.view.k||r.x!==this.view.x||r.y!==this.view.y)&&(this.view={k:r.k,x:r.x,y:r.y}))}tools(){let e=!this.moved&&this.fitK>=1;return A`<div class="tools">
      <button type="button" aria-label=${w(`Zoom out`)} title=${w(`Zoom out (Ctrl + scroll)`)} @click=${()=>this.zoomBy(1/1.25)}>−</button>
      <button type="button" aria-label=${w(`Zoom in`)} title=${w(`Zoom in (Ctrl + scroll)`)} @click=${()=>this.zoomBy(1.25)}>+</button>
      <button type="button" ?disabled=${e} @click=${()=>this.showAll()}>${w(`Show all`)}</button>
    </div>`}showAll(){this.moved=!1,this.fit(),this.requestUpdate()}zoomBy(e,t=this.clientWidth/2,n=this.frameH/2){this.moved=!0,this.view=ga(this.view,e,t,n,Math.min(1,this.fitK)/2,Oo)}onPointerDown(e){e.button!==0||e.target.closest(`.tools`)||this.down&&e.pointerType!==`mouse`||(this.pan={id:e.pointerId,px:e.clientX,py:e.clientY,x:this.view.x,y:this.view.y,far:!1})}onPointerMove(e){let t=this.pan;if(!t||t.id!==e.pointerId)return;let n=e.clientX-t.px,r=e.clientY-t.py;!t.far&&Math.hypot(n,r)<ko||(t.far||(t.far=!0,e.currentTarget.setPointerCapture(e.pointerId),e.currentTarget.classList.add(`drag`)),this.moved=!0,this.view={...this.view,x:t.x+n,y:t.y+r})}onPointerUp(e){let t=this.pan;t&&t.id===e.pointerId&&(this.pan=null,e.currentTarget.classList.remove(`drag`),t.far&&(this.swallowClick=!0))}reveal(e){let t=this.renderRoot.querySelector(`.frame`);if(!t)return;let n=t.getBoundingClientRect(),r=e.getBoundingClientRect(),i=0,a=0;r.left<n.left+24?i=n.left+24-r.left:r.right>n.right-24&&(i=n.right-24-r.right),r.top<n.top+24?a=n.top+24-r.top:r.bottom>n.bottom-24&&(a=n.bottom-24-r.bottom),(i||a)&&(this.moved=!0,this.view={...this.view,x:this.view.x+i,y:this.view.y+a})}get hl(){return this.hover??(this.unit||null)}lit(){let e=this.hl;if(e===null)return null;let t=this.plan.nodes.filter(t=>t.unit?t.unit===e:t.key===e).map(e=>e.key),n=new Set(t),r=e=>{let r=new Set(t),i=[...t];for(let t=i.pop();t!==void 0;t=i.pop())for(let a of e(t))r.has(a)||(r.add(a),n.add(a),i.push(a))};return r(e=>this.waiters.get(e)??[]),r(e=>this.byKey.get(e)?.after??[]),n}render(){if(!this.plan.nodes.length)return A`<div class="blank" style="padding:24px">${this.live?w(`No tasks scheduled yet`):w(`No tasks scheduled`)}</div>`;let e=jr(this.journal,this.plan),t=t=>{let n=e.get(t);return n?pi(n,e,this.run):``},n=this.matrix,r=n?this.matrixView(n,t):this.asTable?this.table():this.dag(t);return A`${this.crumbs()}${r}
      <div class="foot">
        ${this.asTable&&!n?j:this.legend()}
        ${this.asTable||n?j:this.tools()}
        ${n?j:A`<button type="button" class="switch" @click=${()=>this.asTable=!this.asTable}>
              ${this.asTable?w(`Show as graph`):w(`Show as table`)}
            </button>`}
        ${this.asTable&&!n?j:A`<div class="keys">${this.keyHints().map((e,t)=>A`${t?` | `:``}<span>${e}</span>`)}</div>`}
      </div>`}keyHints(){let e=ra(this.segments,this.auto)?w(`Esc: up a level`):``;return(this.matrix?[w(`Arrow keys: marks`),w(`Enter: open`),e]:[w(`Tab: next node`),w(`Arrow keys: marks`),w(`Shift + arrow keys: earlier and later tasks`),w(`Enter: open`),e]).filter(Boolean)}dag(e){let t=this.graphView(e),n=this.view;return A`<div class="frame ${this.down?`down`:``}" style="height:${Math.round(this.frameH)}px"
        @pointerdown=${e=>this.onPointerDown(e)} @pointermove=${e=>this.onPointerMove(e)}
        @pointerup=${e=>this.onPointerUp(e)} @pointercancel=${e=>this.onPointerUp(e)}>
        <div class="stage" style="transform:translate(${n.x}px,${n.y}px) scale(${n.k})">${t}</div>
      </div>`}at(e,t){let n=this.lay?.at[e];if(!n)return`left:0;top:0`;let r=t?t.x+1:0,i=t?t.y+1:0;return`left:${n.x-r}px;top:${n.y-i}px`}graphView(e){let t=this.lit(),n=this.graph,r=this.lay,i=new Map(n.nodes.map(e=>[e.id,e])),a=new Map(n.boxes.map(e=>[e.id,e])),o=new Map(n.stubs.map(e=>[e.id,e])),s=e=>(n.slots[e]??[]).flat().filter(e=>!Y(e)),c=(n,r)=>{let s=a.get(n);if(s)return this.box(s,r,(e,t)=>c(e,t));let l=o.get(n);if(l)return A`<span class="stub" data-id=${l.id} style=${this.at(l.id,r)} title=${w(`Outside this layer`)}>${l.label}</span>`;let u=i.get(n);return u?this.node(u,r,e,t):j},l=!!r&&n.nodes.every(e=>r.at[e.id]),u=r?.w??0,d=r?.h??0;return A`<div class="dag ${this.down?`down`:``} ${t?`hl`:``} ${l?``:`unplaced`}" style="width:${u}px;height:${d}px"
      @mouseleave=${()=>this.hover=null}>
      <svg class="edges" aria-hidden="true" width=${u} height=${d}>
        <defs>
          <marker id="arr" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
            <path d="M0,0.5 L8,4 L0,7.5 z" fill="var(--line2)" stroke="none"></path>
          </marker>
        </defs>
        ${(r?.edges??[]).map(e=>wt`<path class=${e.type} d=${ma(e.runs,r?.down)} marker-end="url(#arr)"></path>`)}
      </svg>
      ${X(s(``),e=>e,e=>c(e,null))}
    </div>`}box(e,t,n){let r=this.lay?.at[e.id]??null,i=()=>this.go([...this.segments,e.id]),a=w(S`Loop at ${this.where(e.loop,e.file)}`),o=e.spread.length>1?ii(e.spread):``,s=(this.graph.slots[e.id]??[]).flat().filter(e=>!Y(e)),c=r?`;width:${r.w}px;height:${r.h}px`:``;return A`<section class="box" role="group" data-box=${e.id} style=${this.at(e.id,t)+c}
        aria-label=${F(a,ni(e.passes),o)}>
      <div class="hd" data-id=${`lbl:${e.id}`}>
        <span class="line">
          <button type="button" class="name" title=${a} aria-label=${w(`Show the passes of the loop`)} @click=${i}>${ai()}</button>
          <span class="count">${ni(e.passes)}</span>
        </span>
        ${o?A`<span class="spread" title=${w(`Units by number of passes`)}>${o}</span>`:j}
      </div>
      <span class="ret" title=${w(`Next pass`)} aria-hidden="true">
        <svg width="14" height="10" viewBox="0 0 14 10"><path d="M11.5,3.5 A4.5,3.6 0 1 1 7,0.9" fill="none" stroke="currentColor" stroke-width="1.4"></path>
          <path d="M6,0 L8.6,1 L6.4,2.9 z" fill="currentColor"></path></svg>
      </span>
      <div class="in">${X(s,e=>e,e=>n(e,r))}</div>
    </section>`}node(e,t,r,i){let a=e.counts,o=a.done+a.skipped,s=a.failed||e.errors?`fail`:a.running?`cur`:o===a.total?`done`:``,c=ca(e),l=c?{id:e.id,label:e.label,slots:Po(e).filter(e=>e?.state===`failed`),grid:{cols:No,size:12,gap:4}}:{id:e.id,label:e.label,slots:Po(e),grid:Fo(e,this.graph.units.length)},u=this.exceptions(e),d=e.type===`flow`?A`<button type="button" class="name" title=${F(w(S`Function ${e.name}`),w(S`${e.calls} flow calls`))}
            aria-label=${w(S`Open ${e.label}`)} @click=${()=>this.go([...this.graph.path,e.name])}>${e.label}</button>`:A`<button type="button" class="name" aria-label=${w(S`Show the tasks of ${e.label}`)}
            @click=${()=>n(this,`ca-navigate`,e.kinds.length===1?{tab:`tasks`,kind:e.kinds[0]}:{tab:`tasks`})}>${e.label}</button>`;return A`<section class="node ${e.type} ${s}" role="group" data-id=${e.id} aria-label=${this.nodeLabel(e)}
      style="${this.at(e.id,t)};--cols:${l.grid.cols};--m:${l.grid.size}px;--g:${l.grid.gap}px">
      <div class="hd">${d}<span class="count" aria-hidden="true" title=${this.doneOf(a)}>${o}/${a.total}</span></div>
      ${c?this.statusBar(e,l,r,i):this.marks(l,r,i)}
      ${u.length?A`<div class="ex" aria-hidden="true">${u.map(([e,t])=>A`<span class=${e}>${t}</span>`)}</div>`:j}
    </section>`}statusBar(e,t,n,r){let i=la(e.counts,wo),a=t.slots.slice(0,No),o=t.slots.length-a.length,s=Math.min(this.active.get(t.id)??0,Math.max(0,a.length-1));return A`<div class="sbar" role="img" aria-label=${this.stateCounts(e.counts)}>
        ${i.map(e=>A`<i class=${e.state} style="width:${e.pct}%" title=${this.countOf(e.state,e.n)}></i>`)}
      </div>
      ${a.length?A`<div class="fails" @keydown=${e=>this.onKey(e,{...t,slots:a,grid:{...t.grid,cols:a.length}})}>
            ${a.map((e,i)=>e?this.mark(t,e,i,i===s,n,r,!0):j)}
            ${o>0?A`<span>${w(S`+${o}`)}</span>`:j}
          </div>`:j}`}marks(e,t,n){let r=Math.min(this.active.get(e.id)??Io(e.slots),e.slots.length-1);return A`<div class="marks ${e.grid.size>=10?`big`:``}" @keydown=${t=>this.onKey(t,e)}>
      ${e.slots.map((i,a)=>i?this.mark(e,i,a,a===r,t,n):A`<span class="slot"></span>`)}
    </div>`}markText(e,t,n,r=``){let i=t.flow?void 0:this.byKey.get(t.key),a=I({kind:e,unit:t.unit}),o=!t.flow&&t.state===`blocked`?n(t.key):``,s=o?w(S`Not started: ${o}`):this.stateWord(t.state),c=i?.attempts??1,l=c>1?w(S`${c} attempts`):``,u=t.passes?ri(t.passes):``,d=t.flow||t.count>1?w(S`${t.count} tasks`):``,f=t.counts?this.notDone(t.counts):[],p=t.error===void 0?[]:[w(`Flow call stopped with an error`),t.error],m=!t.flow&&(t.state===`done`||t.state===`failed`)&&i?.wall_s?N(i.wall_s):``;return{name:a,parts:[s,r,u,l,d,...f,...p,m].filter(Boolean),id:t.flow?w(S`Flow call ${t.key}`):t.key}}open(e){if(e.flow)return this.go([...this.graph.path,e.flow],e.unit||this.unit);let t=this.byKey.get(e.key);n(this,`ca-open-task`,e.state===`blocked`?{key:e.key,view:`input`}:t?.executor===`python`?{key:e.key,view:`output`}:{key:e.key})}mark(e,t,n,r,i,a,o=!1){let{name:s,parts:c,id:l}=this.markText(e.label,t,i),u=t.unit||t.key,d=a!==null&&(t.unit!==``&&t.unit===this.hl||t.keys.some(e=>a.has(e))),f=t=>{this.hover=u,this.active.set(e.id,n),this.reveal(t.currentTarget)};return o?A`<button type="button" class="taskchip ${d?`on`:``}" data-i=${n} tabindex=${r?0:-1}
        title=${[s,...c,l].join(`
`)} aria-label=${F(s,...c)}
        @mouseenter=${()=>this.hover=u} @focus=${f} @blur=${()=>this.hover=null} @click=${()=>this.open(t)}>${t.unit||t.key}</button>`:A`<button type="button" class="mark ${t.state} ${d?`on`:``}" data-i=${n} data-n=${t.passes??j} tabindex=${r?0:-1}
      title=${[s,...c,l].join(`
`)}
      aria-label=${F(s,...c)}
      @mouseenter=${()=>this.hover=u}
      @focus=${f}
      @blur=${()=>this.hover=null}
      @click=${()=>this.open(t)}></button>`}matrixView(e,t){let n=aa(e.rows,this.sort),r=e.columns,i=this.hl,a=r.map((e,t)=>{let n=r[t-1]?.passes;if(!n)return-1;let i=e.passes.findIndex((e,t)=>e!==n[t]);return i<0?e.passes.length===n.length?-1:Math.min(e.passes.length,n.length):i}),o=e=>a[e]===0?`g0`:(a[e]??-1)>0?`g1`:``,s=e.head.length,c=n.length>jo,l=c?Math.max(0,this.scrollRow-Mo):0,u=c?Math.min(n.length,this.scrollRow+60+20):n.length,d=this.cell&&this.cell[0]<n.length?this.cell:this.firstCell(n),f=e.rows.filter(e=>e.unit).length,p=e=>e===0||a[e]===0?`g0`:(a[e]??-1)>0?`g1`:``,m=(t,n,r)=>{let i=`top:${r*22}px`;return t.type===`pass`?A`<th scope="colgroup" colspan=${t.span} class="pass ${p(n)}" style=${i}
          title=${t.box.id===e.box.id?w(S`Loop at ${this.where(t.box.loop,t.box.file)}`):w(S`Nested loop at ${this.where(t.box.loop,t.box.file)}`)}>${ti(t.pass)}</th>`:t.type===`loop`?A`<th scope="colgroup" colspan=${t.span} class="loop ${p(n)}" style=${i}
          title=${w(S`Nested loop at ${this.where(t.box.loop,t.box.file)}`)}>${ai()}</th>`:A`<th scope="col" rowspan=${t.rows} class="nh ${p(n)}" style=${i}
        title=${t.node.type===`flow`?w(S`Function ${t.node.name}`):t.node.label}>${t.node.label}</th>`},h=t=>{let n=[],r=0;for(let i of e.head[t]??[]){for(;Lo(e.head,t,r);)r++;n.push(r),r+=i.span}return n};return A`<div class="mxbar">
        <span>${F(w(S`Loop at ${this.where(e.box.loop,e.box.file)}`),ni(e.box.passes),e.box.spread.length>1?ii(e.box.spread):``,w(f===1?`1 unit`:S`${f} units`))}</span>
        <label>${w(`Sort units`)}
          <select @change=${e=>this.sort=e.target.value}>
            <option value="order" ?selected=${this.sort===`order`}>${w(`Scheduled order`)}</option>
            <option value="passes" ?selected=${this.sort===`passes`}>${w(`Number of passes`)}</option>
            <option value="state" ?selected=${this.sort===`state`}>${w(`Status`)}</option>
          </select>
        </label>
      </div>
      <div class="mx ${i?`hl`:``}" @scroll=${e=>this.onMatrixScroll(e)} @mouseleave=${()=>this.hover=null}>
        <table class="matrix big" role="grid" aria-rowcount=${n.length+s} aria-colcount=${r.length+2}
          aria-label=${F(w(S`Loop at ${this.where(e.box.loop,e.box.file)}`),ni(e.box.passes))}>
          <thead>
            ${e.head.map((e,t)=>{let n=h(t);return A`<tr>
                ${t===0?A`<th scope="col" rowspan=${s} class="uh" style="top:0">${w(`Unit`)}</th>
                      <th scope="col" rowspan=${s} class="pn" style="top:0" title=${w(`Passes of this loop`)}>${w(`Passes`)}</th>`:j}
                ${e.map((e,r)=>m(e,n[r]??0,t))}
              </tr>`})}
          </thead>
          <tbody @keydown=${e=>this.onMatrixKey(e,n)}>
            ${l>0?A`<tr class="gap" aria-hidden="true"><td colspan=${r.length+2} style="height:${l*Ao}px"></td></tr>`:j}
            ${X(n.slice(l,u),e=>e.unit,(e,n)=>{let a=l+n;return A`<tr class=${e.unit&&e.unit===i?`on`:``} aria-rowindex=${a+s+1}>
                  ${e.unit?A`<th scope="row" title=${e.unit}>${e.unit}</th>`:A`<th scope="row" class="none" title=${w(`Tasks that run once per run, not once per unit`)}>${w(`No unit`)}</th>`}
                  <td class="pn ${e.passes>1?`many`:``}">${e.passes}</td>
                  ${e.cells.map((n,i)=>{let s=r[i],c=!!n&&d!==null&&d[0]===a&&d[1]===i;return A`<td class="c ${o(i)}" role="gridcell">${n&&s?this.cellMark(e,n,a,i,s.node,s.passes,c,t):j}</td>`})}
                </tr>`})}
            ${u<n.length?A`<tr class="gap" aria-hidden="true"><td colspan=${r.length+2} style="height:${(n.length-u)*Ao}px"></td></tr>`:j}
          </tbody>
        </table>
      </div>`}cellMark(e,t,n,r,i,a,o,s){let{name:c,parts:l,id:u}=this.markText(i.label,t,s,a.map(ti).join(`, `)),d=t.unit||t.key;return A`<button type="button" class="mark ${t.state} ${e.unit&&e.unit===this.hl?`on`:``}" data-r=${n} data-c=${r} tabindex=${o?0:-1}
      title=${[c,...l,u].join(`
`)} aria-label=${F(c,...l)}
      @mouseenter=${()=>this.hover=d}
      @focus=${()=>{this.hover=d,this.cell=[n,r]}}
      @blur=${()=>this.hover=null}
      @click=${()=>this.open(t)}></button>`}firstCell(e){for(let t=0;t<e.length;t++){let n=e[t]?.cells.findIndex(e=>e!==null)??-1;if(n>=0)return[t,n]}return null}onMatrixScroll(e){let t=Math.floor(e.currentTarget.scrollTop/Ao);Math.abs(t-this.scrollRow)>=Mo/2&&(this.scrollRow=t)}onMatrixKey(e,t){let n=e.target;if(!n.classList.contains(`mark`))return;let r=Number(n.dataset.r),i=Number(n.dataset.c),a=oa(t.map(e=>e.cells.map(e=>e!==null)),r,i,e.key,e.ctrlKey||e.metaKey);if(!a)return;e.preventDefault(),this.cell=a;let o=this.renderRoot.querySelector(`.mx`);if(o&&t.length>jo){let e=a[0]*Ao;(e<o.scrollTop+48||e>o.scrollTop+o.clientHeight-72)&&(o.scrollTop=Math.max(0,e-o.clientHeight/2)),this.scrollRow=Math.floor(o.scrollTop/Ao)}this.requestUpdate(),this.updateComplete.then(()=>this.renderRoot.querySelector(`.matrix .mark[data-r="${a[0]}"][data-c="${a[1]}"]`)?.focus())}stateCounts(e){return F(...wo.filter(t=>e[t]).map(t=>this.countOf(t,e[t])))}doneOf(e){return w(S`${e.done+e.skipped} of ${e.total} tasks done`)}notDone(e){return[`failed`,`blocked`,`running`,`pending`].filter(t=>e[t]).map(t=>this.countOf(t,e[t]))}stateWord(e){return e===`pending`&&!this.live?w(`not run`):$r(e)}where(e,t){let n=t?t.slice(t.lastIndexOf(`/`)+1):``;return n?`${n}:${e}`:w(S`line ${e}`)}countOf(e,t){switch(e){case`blocked`:return K(`not_started`,t);case`pending`:return K(this.live?`waiting`:`not_run`,t);default:return K(e,t)}}exceptions(e){let t=e.counts,n=[];return t.failed&&n.push([`err`,this.countOf(`failed`,t.failed)]),e.errors&&n.push([`err`,e.errors===1?w(`1 flow call stopped with an error`):w(S`${e.errors} flow calls stopped with an error`)]),t.blocked&&n.push([`warn`,this.countOf(`blocked`,t.blocked)]),t.running&&n.push([`live`,this.countOf(`running`,t.running)]),t.pending&&n.push([`mut`,this.countOf(`pending`,t.pending)]),n}neighbours(e){let t=this.graph,n=e=>{let n=t.nodes.find(t=>t.id===e);return n?n.box?w(S`${n.label} in the loop`):n.label:e},r=r=>[...t.stubs.filter(t=>t.to===e.id&&t.type===r).map(e=>e.label),...t.edges.filter(t=>t.to===e.id&&t.type===r).map(e=>n(e.from))];return{waits:r(`after`),after:r(`created`),feeds:[...new Set(t.edges.filter(t=>t.from===e.id).map(e=>n(e.to)))]}}nodeLabel(e){let t=e.counts,{waits:n,after:r,feeds:i}=this.neighbours(e);return[e.type===`flow`?F(w(S`Function ${e.label}`),this.doneOf(t)):F(e.label,this.doneOf(t)),...this.exceptions(e).map(([,e])=>e),n.length?w(S`Waits for ${n.join(`, `)}`):``,r.length?w(S`Created after ${r.join(`, `)}`):``,i.length?w(S`Later tasks: ${i.join(`, `)}`):``].filter(Boolean).join(`. `)}onKey(e,t){let n=e.target;if(!n.classList.contains(`mark`)&&!n.classList.contains(`taskchip`))return;if(e.shiftKey&&e.key.startsWith(`Arrow`))return this.alongEdge(e,t);let{slots:r}=t,i=this.active.get(t.id)??Io(r),a={ArrowRight:1,ArrowLeft:-1,ArrowDown:t.grid.cols,ArrowUp:-t.grid.cols},o;if(e.key===`Home`)o=Io(r);else if(e.key===`End`)o=r.length-1-[...r].reverse().findIndex(e=>e!==null);else if(a[e.key]!==void 0){let t=a[e.key];for(o=i+t;o>=0&&o<r.length&&!r[o];)o+=Math.sign(t);if(o<0||o>=r.length)return}else return;e.preventDefault(),this.active.set(t.id,o),this.requestUpdate();let s=e.currentTarget;this.updateComplete.then(()=>s.querySelector(`[data-i="${o}"]`)?.focus())}alongEdge(e,t){let n=e.key===`ArrowRight`||e.key===`ArrowDown`?`later`:`earlier`,r=this.lay,i=ua(this.graph,t.id,n,e=>{let t=r?.at[e];return t?r?.down?t.x+t.w/2:t.y+t.h/2:0});if(e.preventDefault(),!i)return;let a=this.graph.nodes.find(e=>e.id===i);if(!a)return;let o=t.slots[this.active.get(t.id)??Io(t.slots)]?.unit??``,s=ca(a)?Po(a).filter(e=>e?.state===`failed`):Po(a),c=o?s.findIndex(e=>e?.unit===o):-1,l=c>=0?c:this.active.get(a.id)??Io(s);this.active.set(a.id,l),this.requestUpdate(),this.updateComplete.then(()=>{let e=this.renderRoot.querySelector(`.node[data-id="${CSS.escape(i)}"]`);(e?.querySelector(`[data-i="${l}"]`)??e?.querySelector(`.name`))?.focus()})}legend(){let e=(this.matrix?this.matrix.rows.flatMap(e=>e.cells):this.graph.nodes.flatMap(e=>ca(e)?Po(e).map(e=>e&&{...e,passes:void 0}):Po(e))).filter(e=>e!==null),t=new Set(e.map(e=>e.state)),n=!this.matrix&&e.some(e=>e.passes),r=!this.matrix&&[...this.graph.edges,...this.graph.stubs].some(e=>e.type===`created`),i=e=>wt`<svg width="22" height="8" aria-hidden="true"><path d="M1,4 H21" stroke-dasharray=${e?`5 4`:`none`}></path></svg>`;return A`<div class="legend big">
      ${wo.filter(e=>t.has(e)).map(e=>A`<span aria-hidden="true"><i class="mark ${e}"></i>${this.stateWord(e)}</span>`)}
      ${n?A`<span aria-hidden="true"><i class="mark done" data-n="2"></i>${w(`number of passes`)}</span>`:j}
      ${r?A`<span>${i(!1)}${w(`waits for output`)}</span><span>${i(!0)}${w(`created after result`)}</span>`:j}
    </div>`}table(){let e=this.graph.nodes,t=e.some(e=>e.type===`flow`),n=[...this.graph.edges,...this.graph.stubs].some(e=>e.type===`created`),r=new Map(this.graph.boxes.map(e=>[e.id,e]));return A`<table class="list">
      <thead>
        <tr>
          <th>${w(t?`Kind or function`:`Kind`)}</th><th>${w(`Done`)}</th><th>${w(`Failed`)}</th><th>${w(`Not started`)}</th>
          <th>${w(`Running`)}</th><th>${this.live?w(`Waiting`):w(`Not run`)}</th><th>${w(`Waits for`)}</th>
          ${n?A`<th>${w(`Created after`)}</th>`:j}<th>${w(`Later tasks`)}</th>
        </tr>
      </thead>
      <tbody>
        ${e.map(e=>{let t=e.counts,{waits:i,after:a,feeds:o}=this.neighbours(e),s=e.box?r.get(e.box):void 0;return A`<tr>
            <th scope="row">${e.type===`flow`?A`<button type="button" class="name" @click=${()=>this.go([...this.graph.path,e.name])}>${e.label}</button>`:e.label}${s?A` <button type="button" class="switch" title=${w(`Show the passes of the loop`)} @click=${()=>this.go([...this.segments,s.id])}>${F(ai(),ni(s.passes))}</button>`:j}</th>
            <td class="n">${t.done+t.skipped}/${t.total}</td><td class="n">${t.failed}</td><td class="n">${t.blocked}</td>
            <td class="n">${t.running}</td><td class="n">${t.pending}</td>
            <td>${i.join(`, `)||w(`none`)}</td>
            ${n?A`<td>${a.join(`, `)||w(`none`)}</td>`:j}<td>${o.join(`, `)||w(`none`)}</td>
          </tr>`})}
      </tbody>
    </table>`}};U([V({attribute:!1})],Z.prototype,`plan`,void 0),U([V({attribute:!1})],Z.prototype,`journal`,void 0),U([V()],Z.prototype,`run`,void 0),U([V({type:Boolean})],Z.prototype,`live`,void 0),U([V()],Z.prototype,`layer`,void 0),U([V()],Z.prototype,`unit`,void 0),U([H()],Z.prototype,`hover`,void 0),U([H()],Z.prototype,`asTable`,void 0),U([H()],Z.prototype,`down`,void 0),U([H()],Z.prototype,`lay`,void 0),U([H()],Z.prototype,`view`,void 0),U([H()],Z.prototype,`frameH`,void 0),U([H()],Z.prototype,`sort`,void 0),U([H()],Z.prototype,`scrollRow`,void 0),Z=U([B(`ca-pipeline-graph`),D()],Z);function Io(e){return Math.max(0,e.findIndex(e=>e!==null))}function Lo(e,t,n){for(let r=0;r<t;r++){let i=0;for(let a of e[r]??[]){if(n>=i&&n<i+a.span&&r+a.rows>t)return!0;i+=a.span}}return!1}var Ro=class extends M{constructor(...e){super(...e),this.procs=null,this.plan={nodes:[],groups:[]}}static{this.styles=[z,k`
      :host { display: block; }
      .drv { display: flex; gap: 14px; align-items: flex-start; }
      .drv-ic { width: 42px; height: 42px; border-radius: 12px; flex: none; display: grid; place-items: center; font-size: 16px;
        background: var(--raise); color: var(--mut); }
      .drv.on .drv-ic { background: var(--live-a); box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.35), 0 0 22px rgba(34, 211, 238, 0.18); }
      .drv.on .drv-ic .spin { width: 18px; height: 18px; }
      .drv-t { font-size: 15px; font-weight: 600; }
      .drv-up { font-family: var(--mono); font-size: 12px; color: var(--live); margin-left: 6px; font-weight: 400; }
      .drv-cmd { margin-top: 8px; }
      .drv-cmd summary { cursor: pointer; font-size: 11px; color: var(--mut); }
      .warn { color: var(--warn); }
      .drv-cmd code { display: block; margin-top: 4px; white-space: pre-wrap; word-break: break-all; color: var(--fg2); max-height: 120px; overflow: auto; }
    `]}stateTitle(){if(!this.plan.nodes.length)return[w(`Not running`),``];let e=yi(this.plan);return e.left?[e.left===1?w(`Finished with 1 task not done`):w(S`Finished with ${e.left} tasks not done`),`warn`]:e.failed||e.notStarted?[w(`Finished with errors`),`warn`]:[w(`Finished`),``]}render(){let e=this.procs,t=this.summary;if(!e?.alive){let[e,n]=this.stateTitle(),r=bi(t);return A`<div class="drv off">
        <div class="drv-ic" aria-hidden="true">■</div>
        <div>
          <div class="drv-t ${n}">${e}</div>
          <div class="meta">${F(t?.last_ts?w(S`Ended ${P(t.last_ts,!0)}`):w(`No activity`),r==null?``:w(S`Took ${N(r)}`),t?.run_group?w(S`Run group ${t.run_group}`):``)}</div>
        </div>
      </div>`}let n=Date.parse(e.started_at),r=In.at(`drv:${e.pid??``}`,Number.isNaN(n)?1:(Date.now()-n)/1e3),i=[[w(`PID`),e.pid??`—`],[w(`Run group`),e.run_group],[w(`Running at once (limit)`),e.max_workers||`—`],[w(`Started`),P(e.started_at,!0)]];return A`<div class="drv on">
      <div class="drv-ic"><span class="spin"></span></div>
      <div style="min-width:0">
        <div class="drv-t">${w(`Running`)} <ca-elapsed class="drv-up" .since=${r}></ca-elapsed></div>
        <div class="drv-facts">${i.map(([e,t])=>A`<span><i>${e}</i>${t}</span>`)}</div>
        <details class="drv-cmd"><summary>${w(`Command line`)}</summary><code>${e.argv.join(` `)}</code></details>
      </div>
    </div>`}};U([V({attribute:!1})],Ro.prototype,`procs`,void 0),U([V({attribute:!1})],Ro.prototype,`summary`,void 0),U([V({attribute:!1})],Ro.prototype,`plan`,void 0),Ro=U([B(`ca-run-driver`),D()],Ro);var zo=e=>new Date(e).toLocaleTimeString(Jt(),{hour:`2-digit`,minute:`2-digit`,hourCycle:`h23`}),Bo=e=>new Date(e).toLocaleTimeString(Jt(),{hour:`2-digit`,minute:`2-digit`,second:`2-digit`,hourCycle:`h23`}),Vo=6e5,Ho=class extends M{constructor(...e){super(...e),this.journal=[],this.procs=null,this.live=!1,this.run=``,this.drawnRun=null,this.timer=null}static{this.styles=[z,k`
      :host { display: block; }
      .tl { position: relative; }
      .tl-axis { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 10px; color: var(--mut); margin: 0 0 6px 120px; }
      .tl-row { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 8px; align-items: center; min-height: 24px; padding: 4px 0; }
      .nm { font-size: 11.5px; color: var(--fg2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .nm.llm { color: var(--llm); }
      .tl-lane { position: relative; height: calc(var(--tracks, 1) * 14px + 2px); border-radius: 4px;
        background: repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.03) 0 1px, transparent 1px 10%); }
      .tl-bar { position: absolute; top: calc(var(--track, 0) * 14px + 2px); height: 12px; border-radius: 4px; min-width: 3px; cursor: default;
        transform-origin: left center; transition: width 1s linear; }
      .tl.anim .tl-bar:not(.run) { animation: growx 0.6s var(--ease) both; }
      .tl-bar.py { background: linear-gradient(90deg, #64748b, #94a3b8); }
      .tl-bar.llm { background: linear-gradient(90deg, #7c3aed, #a78bfa); }
      .tl-bar.bad { background: linear-gradient(90deg, #b91c1c, #f87171); }
      .tl-bar.idle { background: var(--line2); }
      .tl-bar.run { background: repeating-linear-gradient(45deg, var(--live) 0 6px, #0891b2 6px 12px); background-size: 17px 17px;
        animation: stripes 0.8s linear infinite; box-shadow: 0 0 12px rgba(34, 211, 238, 0.5); }
      .tl-bar:hover { filter: brightness(1.25); }
      .tl-now { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--live); border-radius: 2px; box-shadow: 0 0 10px var(--live); }
      .legend { margin-top: 10px; }
      .legend + .legend { margin-top: 4px; }
      @media (max-width: 760px) {
        .tl-row { grid-template-columns: 78px minmax(0, 1fr); }
        .tl-axis { margin-left: 86px; }
      }
    `]}updated(e){e.has(`live`)&&this.tick(this.live)}connectedCallback(){super.connectedCallback(),this.tick(this.live)}disconnectedCallback(){super.disconnectedCallback(),this.tick(!1)}tick(e){e&&!this.timer&&(this.timer=setInterval(()=>this.requestUpdate(),1e3)),!e&&this.timer&&(clearInterval(this.timer),this.timer=null)}render(){let e=Date.now(),t=this.live?Tr(this.procs).map(t=>({kind:t.kind,cls:t.cls,t0:In.at(t.id,t.ageS,e)})):[],n=ba(this.journal,t,e);if(!n)return A`<div class="blank" style="padding:28px"><span class="ic" aria-hidden="true">⏱</span>${this.live?w(`No finished attempts yet`):w(`No finished attempts`)}</div>`;let r=this.drawnRun!==this.run;this.drawnRun=this.run;let i=jr(this.journal,{nodes:[],groups:[]}),a=(e,t)=>{let n=t.row;if(!n)return`${e}\n${w(`running`)}`;if(!G(n)){let e=i.get(n.key),t=n.stop===`invalid_input`&&e?pi(e,i,this.run):``;return[I(n),t?w(S`Not started: ${t}`):q(n.stop,n.reason),n.key].join(`
`)}let r=ui(n.hops),a=n.reason&&!n.ok?J(n.reason,this.run):``;return[I(n),F(q(n.stop),N(n.wall_s),w(S`ended ${Bo(t.end)}`)),r?w(S`Model switch: ${r}`):n.model?w(S`Model ${n.model}`):``,a,n.key].filter(Boolean).join(`
`)},o=Math.min(1,(e-n.t0)/n.span),s=n.span<Vo?Bo:zo;return A`<div class="tl ${r?`anim`:``}">
        <div class="tl-axis">${[0,.25,.5,.75,1].map(e=>A`<span>${s(n.t0+n.span*e)}</span>`)}</div>
        ${X(n.lanes,e=>e.name,t=>A`<div class="tl-row">
            <span class="nm ${t.llm?`llm`:``}" title=${t.name}>${t.name}</span>
            <div class="tl-lane" style="--tracks:${t.tracks}">
              ${t.bars.map(r=>{let i=xa(r,n,e);return A`<span class="tl-bar ${r.cls}" style="--track:${r.track};left:${i.left.toFixed(3)}%;width:${i.width.toFixed(3)}%" title=${a(t.name,r)}></span>`})}
            </div>
          </div>`)}
        ${n.live?A`<span class="tl-now" style="left:calc(120px + (100% - 120px) * ${o.toFixed(4)})"></span>`:j}
      </div>
      <div class="legend">
        <span><i style="background:#94a3b8"></i>${w(`Python task`)}</span><span><i style="background:#a78bfa"></i>${w(`Agent task`)}</span>
      </div>
      <div class="legend">
        <span><i style="background:#22d3ee"></i>${w(`running`)}</span><span><i style="background:#f87171"></i>${w(`failed`)}</span>
        <span><i style="background:var(--line2)"></i>${w(`not started`)}</span>
        ${n.hidden?A`<span>${n.hidden===1?w(`1 older attempt not shown`):w(S`${n.hidden} older attempts not shown`)}</span>`:j}
      </div>`}};U([V({attribute:!1})],Ho.prototype,`journal`,void 0),U([V({attribute:!1})],Ho.prototype,`procs`,void 0),U([V({type:Boolean})],Ho.prototype,`live`,void 0),U([V()],Ho.prototype,`run`,void 0),Ho=U([B(`ca-timeline`),D()],Ho);var Uo=class extends M{constructor(...e){super(...e),this.procs=null,this.live=!1}static{this.styles=[z,k`
      :host { display: block; }
      .wks { display: grid; grid-template-columns: repeat(var(--n, 3), minmax(0, 1fr)); gap: 10px; }
      @media (max-width: 900px) { .wks { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      .wk { border-radius: 11px; padding: 10px 12px; border: 1px solid var(--line); background: rgba(255, 255, 255, 0.02); min-width: 0;
        position: relative; overflow: hidden; }
      .wk.py { border-color: rgba(148, 163, 184, 0.35); }
      .wk.llm { border-color: rgba(167, 139, 250, 0.45); background: var(--llm-a); cursor: pointer; }
      .wk.idle { opacity: 0.45; border-style: dashed; }
      .wk-top { display: flex; align-items: center; gap: 8px; min-width: 0; }
      .wk-top b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .wk-ic { width: 24px; height: 24px; border-radius: 7px; flex: none; display: grid; place-items: center; background: var(--raise); font-size: 12px; }
      .wk.llm .wk-ic { color: var(--llm); }
      .wk.py .wk-ic { color: var(--muted); }
      .wk-el { margin-left: auto; font-family: var(--mono); font-size: 11.5px; color: var(--live); }
      .wk-bar { position: absolute; left: 0; right: 0; bottom: 0; height: 2px; overflow: hidden; }
      .wk-bar i { position: absolute; top: 0; bottom: 0; width: 30%; background: linear-gradient(90deg, transparent, var(--live), transparent);
        animation: scan 1.8s linear infinite; }
      .wk.llm .wk-bar i { background: linear-gradient(90deg, transparent, var(--llm), transparent); }
    `]}render(){let e=this.live?Tr(this.procs):[],t=Math.max(this.procs?.max_workers||1,e.length),r=Array.from({length:t-e.length},(e,t)=>t);return A`<div class="wks" style="--n:${Math.min(t,6)}">
      ${X(e,e=>e.id,e=>A`<div class="wk ${e.cls}"
          @click=${e.key?()=>n(this,`ca-open-task`,{key:e.key}):j}>
          <div class="wk-top"><span class="wk-ic" title=${e.cls===`llm`?w(`Agent task`):w(`Python task`)}><span aria-hidden="true">${e.cls===`llm`?`✦`:`⚙`}</span><span class="sr">${e.cls===`llm`?w(`Agent task`):w(`Python task`)}</span></span><b>${e.kind}</b>
            <ca-elapsed class="wk-el" .since=${In.at(e.id,e.ageS)}></ca-elapsed></div>
          <div class="meta">${e.detail}</div>
          <div class="wk-bar"><i></i></div>
        </div>`)}
      ${r.map(()=>A`<div class="wk idle"><div class="wk-top"><b>${w(`Idle`)}</b></div>
          <div class="meta">${w(`No task`)}</div></div>`)}
    </div>`}};U([V({attribute:!1})],Uo.prototype,`procs`,void 0),U([V({type:Boolean})],Uo.prototype,`live`,void 0),Uo=U([B(`ca-workers`),D()],Uo);var Wo=5,Go=[`invalid`,`refused`,`failed`,`running`,`pending`,`valid`];function Ko(e){if(e===void 0)return w(`Loading…`);if(typeof e!=`object`||!e)return JSON.stringify(e);let t=Object.keys(e);if(!t.length)return w(`Empty`);let n=`${t.slice(0,4).join(`, `)}${t.length>4?`, …`:``}`;return w(Array.isArray(e)?S`${t.length} items: ${n}`:S`${t.length} keys: ${n}`)}var qo=class extends M{constructor(...e){super(...e),this.run=``,this.layer=``,this.unit=``}static{this.styles=[z,k`
      :host { display: block; }
      .ct-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
      .pcards { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(320px, 100%), 1fr)); gap: 12px; }
      .pcard { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 12px; align-items: start; padding: 12px 14px; border-radius: 10px;
        background: var(--raise); border: 1px solid var(--line); cursor: pointer; transition: border-color 0.15s, transform 0.15s;
        text-align: left; color: inherit; font: inherit; width: 100%; min-width: 0; }
      .pcard > div { min-width: 0; }
      .pcard .meta { overflow-wrap: anywhere; }
      .pcard:hover { border-color: var(--llm); transform: translateY(-1px); }
      .pc-ic { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 9px; background: var(--llm-a); color: var(--llm); font-size: 16px; }
      .pc-peek { font-family: var(--mono); font-size: 11.5px; color: var(--fg2); margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .pc-go { grid-column: 2; color: var(--llm); font-size: 12px; opacity: 0.8; margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .pcard:hover .pc-go { opacity: 1; }
      .cur-units { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px 14px; }
      .cu { display: grid; grid-template-columns: 90px 1fr 70px auto; gap: 8px; align-items: center; }
      .cu-bar { height: 5px; border-radius: 3px; background: var(--track); overflow: hidden; }
      .cu-bar i { display: block; height: 100%; background: var(--live); }
      .fl > div.meta { grid-column: 1 / 4; overflow: hidden; text-overflow: ellipsis; }
      .stopped { grid-column: 1 / 4; color: var(--mut); font-size: 11px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
      .fl.muted { opacity: 0.7; }
      .fl.muted .jstop { color: var(--ok); }
      .next { margin: 10px 2px 2px; font-size: 12px; color: var(--fg2); }
      .next code { font-family: var(--mono); }
      .more { font-size: 12px; margin: 6px 10px 0; }
    `]}go(e){n(this,`ca-navigate`,{tab:e})}open(e){n(this,`ca-open-task`,{key:e.key,...W(e)?{view:`output`}:{}})}render(){let e=this.state,t=wr(e,this.summary),r=t?Tr(e.procs).length:0,i=e.procs?.max_workers||1,a=this.info.panels;return A`<div class="g12">
      <section class="panel c5 enter">
        <h3>${w(`Run`)}</h3>
        <ca-run-driver .procs=${e.procs} .summary=${this.summary} .plan=${e.plan}></ca-run-driver>
      </section>
      <section class="panel c7 enter">
        <h3 title=${w(`Limit: max_concurrent`)}>${w(`Running tasks`)}
          ${t?A`<span class="r">${w(S`${r} of ${i} running at once`)}</span>`:j}</h3>
        ${t?A`<ca-workers .procs=${e.procs} .live=${t}></ca-workers>`:A`<div class="meta">${w(`No tasks running`)}</div>`}
      </section>
      <section class="panel c12 enter">
        <h3 title=${w(`Every task the run scheduled, by kind (plan.jsonl)`)}>${w(`Pipeline`)}
          <span class="r">${this.progressLine(t)}</span></h3>
        <ca-pipeline-graph .plan=${e.plan} .journal=${e.journal} .run=${this.run} .layer=${this.layer} .unit=${this.unit} ?live=${t}></ca-pipeline-graph>
      </section>
      <section class="panel c12 enter">
        <h3 title=${w(`Counted from every finished attempt (journal.jsonl)`)}>${w(`Totals`)}</h3>
        <ca-kpis .journal=${e.journal} .plan=${e.plan}></ca-kpis>
      </section>
      ${Br(e.journal)?A`<section class="panel c12 enter">
            <h3 title=${w(`Reported by the coding agents`)}>${w(`Tokens and cost by kind`)}</h3>
            <ca-spend-breakdown .journal=${e.journal}></ca-spend-breakdown>
          </section>`:j}
      ${qr(e.journal).length?A`<section class="panel c12 enter">
            <h3 title=${w(`Reported at each agent session start. Account-wide: every task that runs at once shares it.`)}>
              ${w(`Subscription usage`)}<span class="r">${w(`Per account, first → last reading`)}</span></h3>
            <ca-quota .journal=${e.journal}></ca-quota>
          </section>`:j}
      <section class="panel ${t?`c5`:`c12`} enter">
        <h3>${w(`Problems`)}
          <span class="r"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>n(this,`ca-navigate`,{tab:`journal`,stop:`bad`}))}>${w(`Failed attempts in history`)}</a></span></h3>
        ${this.problems(t)}
      </section>
      ${t?A`<section class="panel c7 enter">
            <h3>${w(`Process tree`)}
              <span class="r"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>this.go(`procs`))}>${w(`All processes`)}</a></span></h3>
            <ca-proc-tree .procs=${e.procs}></ca-proc-tree>
          </section>`:j}
      <section class="panel c12 enter">
        <h3 title=${w(`Checked files (OutputContract, InputContract)`)}>${w(`Outputs`)}
          <span class="r"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>this.go(`outputs`))}>${w(`All outputs`)}</a></span></h3>
        ${this.outputs()}
      </section>
      ${e.cursor?A`<section class="panel c12 enter">
            <h3 title=${w(`Stage and step per unit (CursorStore)`)}>${w(`Resume cursor`)}</h3>
            ${this.cursor()}
          </section>`:j}
      ${a.length?A`<section class="panel c12 enter">
            <h3 title=${w(`monitor.Panel`)}>${w(`Custom views`)}</h3>
            ${this.panelCards()}
          </section>`:j}
      <section class="panel c12 enter">
        <h3>${w(`Timeline`)}
          <span class="r">${this.triesLine()}</span></h3>
        <ca-timeline .journal=${e.journal} .procs=${e.procs} .live=${t} .run=${this.run}></ca-timeline>
      </section>
    </div>`}outputs(){let{contracts:e,tally:t}=this.state.outputs;if(!e.length)return A`<div class="meta">${w(`No output files`)}</div>`;let n=Go.filter(e=>t[e]),r=e.flatMap(e=>(e.outputs??[]).map(t=>[e,t])).filter(([,e])=>e.status===`invalid`||e.status===`failed`),i=r.slice(0,Wo),a=t.refused;return A`<div class="ct-row">
        ${n.length?n.map(e=>A`<span class="ct-chip ${e}" title=${Ja(e)}>${qa(e)} <b>${t[e]}</b></span>`):A`<span class="meta">${w(`No checked files`)}</span>`}
      </div>
      ${i.map(([e,t])=>A`<div class="fl" @click=${()=>this.go(`outputs`)}>
          <span class="jstop j-${eo(t.status)}" title=${t.status?Ja(t.status):``}>${t.status?qa(t.status):`—`}</span>
          <b class="jmono" title=${e.key}>${I({kind:e.kind,unit:e.unit===e.key?``:e.unit})}</b>
          <span class="meta">${lo(t)}</span>
          <div class="meta">${J(t.errors?.[0]||t.path,this.run).slice(0,160)}</div>
        </div>`)}
      ${r.length>i.length?A`<div class="more"><a class="lnk" href="#" @click=${e=>this.nav(e,()=>this.go(`outputs`))}>${r.length-i.length===1?w(`1 more output`):w(S`${r.length-i.length} more outputs`)}</a></div>`:j}
      ${a?A`<div class="meta more">${w(a===1?`1 output not written (task not started)`:S`${a} outputs not written (tasks not started)`)}</div>`:j}`}progressLine(e){let t=this.state.plan,n=yi(t);if(e||n.left){let e=_i(t);return F(w(S`${e.pct}%`),w(S`${e.done} of ${e.total} tasks done`))}return F(K(`done`,n.done),n.failed?K(`failed`,n.failed):``,n.notStarted?K(`not_started`,n.notStarted):``)}triesLine(){let{tries:e,notStarted:t}=vi(this.state.journal);return F(w(e===1?`1 attempt`:S`${e} attempts`),t?K(`not_started`,t):``)}nav(e,t){e.preventDefault(),t()}cursor(){let e=this.state.cursor,t=Object.entries(e?.units??{});if(!e||!e.stage&&!t.length)return A`<div class="meta">${w(`No resume cursor`)}</div>`;let n=e.completed_stages??[];return A`<div class="chips" style="margin-bottom:10px">
        ${n.length||e.stage?A`${n.map(e=>A`<span class="chip done"><span aria-hidden="true">✓</span><span class="sr">${w(`done`)}</span> ${e}</span>`)}${e.stage?A`<span class="chip cur"><span class="sr">${w(`current`)}</span>${e.stage}</span>`:j}`:A`<span class="meta">${w(`No stage`)}</span>`}
      </div>
      ${t.length?A`<div class="cur-units">
            ${t.map(([e,t])=>A`<div class="cu">
                <span class="jmono">${e}</span>
                <span class="meta">${F(t.step||`—`,t.loop_pass?w(S`loop pass ${t.loop_pass}`):``)}</span>
                <span class="cu-bar" title=${t.completed.length===1?w(`1 step completed`):w(S`${t.completed.length} steps completed`)}><i style="width:${Math.min(100,12*(t.completed.length+1))}%"></i></span>
                ${t.inflight.length?A`<span class="pill p-running" title=${t.inflight.join(`
`)}>${w(`running`)}</span>`:j}
              </div>`)}
          </div>`:j}`}panelCards(){return A`<div class="pcards">
      ${X(this.info.panels,e=>e.name,e=>A`<button type="button" class="pcard" @click=${()=>this.go(`panel:${e.name}`)}>
          <span class="pc-ic" aria-hidden="true">${e.icon||`▤`}</span>
          <div>
            <b>${e.title||e.name}</b>
            ${e.description?A`<div class="meta">${e.description}</div>`:j}
            <div class="pc-peek">${Ko(this.state.panels[e.name])}</div>
          </div>
          <span class="pc-go">${w(S`Show ${e.title||e.name}`)}</span>
        </button>`)}
    </div>`}name(e){return I(e)}problems(e){let t=jr(this.state.journal,this.state.plan),{failed:n,notStarted:r}=Mr(t),i=[...t.values()].filter(e=>e.outcome===`recovered`);if(!n.length&&!r.length&&!i.length)return A`<div class="blank" style="padding:22px"><span class="ic" aria-hidden="true">✓</span>${w(`No problems`)}</div>`;let a=e=>J(e.attempts[e.attempts.length-1]?.reason||`—`,this.run).slice(0,200),o=e=>e.length?A`<div class="stopped">
            <span>${e.length===1?w(`1 later task not started`):w(S`${e.length} later tasks not started`)}</span>
            ${e.map(e=>Aa(this,this.name(e),e))}
          </div>`:j;return A`${X(n,e=>e.task.key,e=>{let t=e.task.attempts[e.task.attempts.length-1];return A`<div class="fl" @click=${()=>this.open(e.task)}>
            <span class="jstop j-error">${Yr(`failed`)}</span>
            <b class="jmono" title=${e.task.key}>${this.name(e.task)}</b><span class="meta">${P(t?.ts,!0)}</span>
            <div class="meta">${q(t?.stop)}: ${a(e.task)}</div>
            ${o(e.stopped)}
          </div>`})}
      ${X(r,e=>e.key,e=>A`<div class="fl" @click=${()=>this.open(e)}>
          <span class="jstop j-invalid_input">${Yr(`not_started`)}</span>
          <b class="jmono" title=${e.key}>${this.name(e)}</b><span></span>
          <div class="meta">${pi(e,t,this.run)?rn(pi(e,t,this.run)):a(e)}</div>
        </div>`)}
      ${X(i,e=>e.key,e=>{let t=e.tries.filter(e=>!e.ok).length,n=e.tries.length,r=this.name(e);return A`<div class="fl muted" @click=${()=>this.open(e)}>
            <span class="jstop">${Yr(`recovered`)}</span>
            <b class="jmono" title=${e.key}>${r}</b><span></span>
            <div class="meta">${w(t===1?S`Done on attempt ${n} after 1 failed attempt`:S`Done on attempt ${n} after ${t} failed attempts`)}</div>
          </div>`})}
      ${this.nextStep(e,n.length+r.length)}`}nextStep(e,t){if(e||!t)return j;let n=Nr(jr(this.state.journal,this.state.plan)),r=n.total-n.done-n.recovered-n.skipped;return r?A`<div class="next" title="resume=True">${w(S`${r} of ${n.total} tasks not done`)}</div>`:j}};U([V({attribute:!1})],qo.prototype,`state`,void 0),U([V({attribute:!1})],qo.prototype,`summary`,void 0),U([V({attribute:!1})],qo.prototype,`info`,void 0),U([V()],qo.prototype,`run`,void 0),U([V()],qo.prototype,`layer`,void 0),U([V()],qo.prototype,`unit`,void 0),qo=U([B(`ca-overview`),D()],qo);function Jo(e,t,n){let r=n.toLowerCase();return e.filter(e=>(!t||e.kind===t)&&(!r||`${e.kind} ${e.unit} ${e.key} ${e.last_stop}`.toLowerCase().includes(r)))}var Yo={failed:0,not_started:1,running:2,waiting:3};function Xo(e){return e.map((e,t)=>({t:e,i:t})).sort((e,t)=>(Yo[e.t.outcome]??9)-(Yo[t.t.outcome]??9)||t.t.last_ts.localeCompare(e.t.last_ts)||e.i-t.i).map(e=>e.t)}var Zo=[`key`,`unit`,`stop`,`kind`,`route`,`reason`];function Qo(e){let t=new Map;for(let n of e)G(n)&&t.set(n.key,(t.get(n.key)??0)+1);return new Set([...t].filter(([,e])=>e>1).map(([e])=>e))}var $o=e=>(e.rounds??1)>1;function es(e,t,n,r){let i=r.toLowerCase(),a=n===`retried`?Qo(e):null;return e.filter(e=>n===`bad`&&!xr(e)||n===`fixup`&&!$o(e)||a&&!a.has(e.key)||n&&![`bad`,`fixup`,`retried`].includes(n)&&e.stop!==n||t&&e.kind!==t?!1:!i||Zo.some(t=>String(e[t]??``).toLowerCase().includes(i)))}function ts(e){let t=new Map;for(let n of e)t.set(n.stop||`?`,(t.get(n.stop||`?`)??0)+1);return[...t.entries()].sort((e,t)=>t[1]-e[1])}function ns(e){let t=new Map;return e.forEach((e,n)=>{let r=t.get(e.key)??{count:0,lastOk:-1,lastOkTry:0};G(e)&&r.count++,e.ok&&(r.lastOk=n,r.lastOkTry=(e.attempt??0)+1),t.set(e.key,r)}),t}var rs=class extends M{constructor(...e){super(...e),this.journal=[],this.plan=null,this.kind=``,this.q=``,this.live=!1,this.run=``}static{this.styles=[z,k`
      :host { display: block; margin-top: 4px; }
      /* the numbers sit tight together, right-aligned; the outcome comes last and takes the spare width, so no gap opens inside the row */
      .trow { display: grid; grid-template-columns: minmax(220px, 0.6fr) 64px 132px 72px 72px 128px minmax(240px, 1fr);
        column-gap: 20px; padding: 6px 12px; align-items: center; border-radius: 8px; transition: background 0.15s; cursor: pointer; }
      .trow.hd { cursor: default; }
      .trow:not(.hd):hover { background: var(--raise); }
      .trow.running { background: var(--live-a); }
      .trow.hd { align-items: end; white-space: nowrap; padding: 4px 12px 8px; color: var(--mut); font-size: 11px; border-bottom: 1px solid var(--line); border-radius: 0; margin-bottom: 4px; }
      .num { text-align: right; font-variant-numeric: tabular-nums; }
      .wall { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
      .wall .jdur { width: 56px; margin: 0; flex: none; }
      .grow { display: flex; align-items: center; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .grow .jdim { margin-left: 8px; }
      .pass { margin-left: 8px; font-size: 11px; color: var(--mut); }
      .cause { display: block; font-size: 11px; color: var(--mut); margin-top: 2px; white-space: normal; overflow-wrap: anywhere; }
      @media (max-width: 760px) {
        .trow { grid-template-columns: minmax(0, 1fr) 128px 90px; }
        .trow > span:nth-child(2), .trow > span:nth-child(4), .trow > span:nth-child(5), .trow > span:nth-child(6) { display: none; }
      }
    `]}cause(e,t){return e.outcome===`not_started`?pi(e,t,this.run):e.outcome===`waiting`?Zr(e.waits_for.map(e=>t.get(e)??{kind:e})):``}spendCells(e,t){return e?t?.reported?A`<span class="num" title=${F(w(S`Cache read ${R(t.cache_read)}`),w(S`Cache write ${R(t.cache_creation)}`))}>${R(t.input+t.output)}</span><span class="num">${on(t.cost)}</span>`:A`<span class="num jdim">—</span><span class="num jdim">—</span>`:A`<span class="num jdim">${w(`none`)}</span><span class="num jdim">${w(`none`)}</span>`}render(){let e=this.plan?Ir(this.journal,this.plan):[],t=Xo(Jo(e,this.kind,this.q));if(!t.length)return A`<div class="blank"><span class="ic" aria-hidden="true">≡</span>${e.length?w(`No tasks match the filter`):w(`No tasks`)}</div>`;let r=new Map(e.map(e=>[e.key,e])),i=new Map;for(let t of e)i.set(`${t.kind}|${t.unit}`,(i.get(`${t.kind}|${t.unit}`)??0)+1);let a=Math.max(1,...t.map(e=>e.wall_s)),o=new Map;for(let e of this.journal)zr(o.get(e.key)??o.set(e.key,Lr()).get(e.key),e);return A`<div class="trow hd">
        <span title=${w(`Kind · unit`)}>${w(`Task`)}</span><span class="num" title=${w(`Attempts that ran`)}>${w(`Attempts`)}</span>
        <span class="num" title=${w(`Sum over all attempts`)}>${w(`Time`)}</span>
        <span class="num" title=${w(`Input and output tokens, all attempts`)}>${w(`Tokens`)}</span>
        <span class="num" title=${w(`Reported by the coding agent`)}>${w(`Cost`)}</span>
        <span class="num">${w(`Last attempt ended`)}</span>
        <span class="st">${w(`Status`)}</span>
      </div>
      ${X(t,e=>e.key,e=>{let t=W(e),s=e.outcome===`running`,c=e.tries.length>0,l=this.cause(e,r),u=e.pass!==null&&(i.get(`${e.kind}|${e.unit}`)??0)>1?e.pass:null;return A`<div class="trow ${s?`running`:``} ${t?`py`:``}"
            @click=${()=>n(this,`ca-open-task`,t?{key:e.key,view:`output`}:{key:e.key})}>
            <span class="grow jmono" title=${e.key}>
              <span class="k-ic ${t?``:`llm`}" title=${w(t?`Python task`:`Agent task`)}><span aria-hidden="true">${t?`⚙`:`✦`}</span><span class="sr">${w(t?`Python task`:`Agent task`)}</span></span>${e.kind}
              ${e.unit?A`<span class="jdim">· ${e.unit}</span>`:j}${u===null?j:A`<span class="pass">${ti(u)}</span>`}
            </span>
            <span class="num">${e.tries.length}</span>
            <span class="num wall">${c?A`${N(e.wall_s)}<span class="jdur"><i class=${t?``:`llm`}
                  style="width:${Math.max(4,Math.round(100*e.wall_s/a))}%"></i></span>`:A`<span class="jdim">${w(`none`)}</span><span class="jdur" style="visibility:hidden"></span>`}</span>
            ${this.spendCells(c,o.get(e.key))}
            <span class="num meta">${c?P(e.tries[e.tries.length-1]?.ts,!0):w(`none`)}</span>
            <span class="st"><span class="pill o-${e.outcome}" title=${e.last_stop}>${Xr(e.outcome,this.live)}</span>${l?A`<span class="cause">${l}</span>`:j}</span>
          </div>`})}`}};U([V({attribute:!1})],rs.prototype,`journal`,void 0),U([V({attribute:!1})],rs.prototype,`plan`,void 0),U([V()],rs.prototype,`kind`,void 0),U([V()],rs.prototype,`q`,void 0),U([V({type:Boolean})],rs.prototype,`live`,void 0),U([V()],rs.prototype,`run`,void 0),rs=U([B(`ca-task-table`),D()],rs);var is=`grid-template-columns:64px minmax(130px,0.8fr) minmax(150px,0.7fr) minmax(150px,1fr) 92px 60px 76px minmax(200px,2.2fr)`,as=class extends M{constructor(...e){super(...e),this.rows=[],this.fresh=new Set,this.kind=``,this.stop=``,this.q=``,this.run=``,this.outcomes=new Map}static{this.styles=[z,k`
      :host { display: block; }
      .jtally { display: flex; flex-wrap: wrap; gap: 8px; padding: 2px 0 12px; }
      .jchip { border: 1px solid var(--line); border-radius: 999px; padding: 3px 11px; font-size: 11.5px; color: var(--mut);
        cursor: pointer; transition: all 0.15s; background: none; }
      .jchip b { color: var(--fg); }
      .jchip:hover { border-color: var(--line2); color: var(--fg); }
      .jchip.on { background: var(--raise); color: var(--fg); }
      .jchip.j-completed { color: var(--ok); border-color: rgba(52, 211, 153, 0.35); }
      .jchip.j-max_turns, .jchip.j-timeout, .jchip.j-stalled { color: var(--warn); border-color: rgba(251, 191, 36, 0.35); }
      .jchip.j-error, .jchip.j-launch_failed, .jchip.j-no_output { border-color: #6b2b2b; color: #e5534b; }
      .table { overflow-x: auto; }
      .jrow { display: grid; column-gap: 12px; row-gap: 2px; padding: 7px 12px; border-bottom: 1px solid var(--line); font-size: 12px; align-items: center; min-width: 980px; }
      .jrow > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
      .jrow > span.jstop { white-space: normal; }
      .jrow:hover { background: var(--card); }
      .jrow.hd { color: var(--mut); font-size: 11px; position: sticky; top: 0; background: var(--bg); z-index: 1; }
      .jrow.bad { background: rgba(248, 113, 113, 0.07); box-shadow: inset 3px 0 0 var(--err); }
      .jrow.py { opacity: 0.85; }
      .jrow.py:hover, .jrow.py.bad { opacity: 1; }
      .jrow.fresh { animation: rowin 1.6s var(--ease); }
      .jrow.agent { cursor: pointer; }
      .num { text-align: right; font-variant-numeric: tabular-nums; }
      .jwhy { color: var(--fg2); white-space: normal !important; overflow-wrap: anywhere; }
      .later { color: var(--ok); }
      .nw { white-space: nowrap; }
      .jrow.notrun { opacity: 0.8; }
      .jstop.j-invalid_input, .jchip.j-invalid_input { color: var(--warn); }
      .unread { color: var(--warn); }
      .jchip.j-fixup, .jchip.j-retried { color: var(--warn); border-color: rgba(251, 191, 36, 0.35); }
      .two { display: flex; flex-direction: column; line-height: 1.35; }
      .two .sub { color: var(--mut); font-size: 11px; white-space: normal; overflow-wrap: anywhere; }
      .num.two > span { white-space: nowrap; }
      .jrow > span.two { white-space: normal; }
      .sub .q { color: var(--live); font-family: var(--mono); white-space: nowrap; }
      .jstop .sub { font-weight: 400; }
      .cost { font-variant-numeric: tabular-nums; text-align: right; color: var(--fg2); }
    `]}render(){this.outcomes=jr(this.rows,{nodes:[],groups:[]});let e=es(this.rows,this.kind,this.stop,this.q).reverse(),t=Math.max(1,...e.map(e=>e.wall_s||0)),r=ns(this.rows),i=new Map(this.rows.map((e,t)=>[e,t])),a=this.rows.filter($o).length,o=Qo(this.rows).size,s=(e,t,r,i)=>A`<button type="button" class="jchip j-${e} ${this.stop===e?`on`:``}" title=${i}
        @click=${()=>n(this,`ca-filter`,{stop:this.stop===e?``:e})}>${t} <b>${r}</b></button>`;return A`<div class="jtally">
        ${ts(this.rows).map(([e,t])=>s(e,this.shortStop(e),t,e))}
        ${a?s(`fixup`,w(`attempts with corrections`),a,w(`Attempts with at least one correction`)):j}
        ${o?s(`retried`,w(`tasks retried`),o,w(`Tasks with more than one attempt`)):j}
      </div>
      <div class="table">
      <div class="jrow hd" style=${is}>
        <span>${w(`Ended`)}</span><span>${w(`Task`)}</span>
        <span title=${w(`How the attempt ended (stop)`)}>${w(`Outcome`)}</span>
        <span>${w(`Agent, model, identity`)}</span>
        <span class="num" title=${w(`Input / output tokens, then cache read / cache write`)}>${w(`Tokens`)}</span>
        <span class="num" title=${w(`Reported by the coding agent`)}>${w(`Cost`)}</span>
        <span class="num">${w(`Time`)}</span><span>${w(`Reason`)}</span>
      </div>
      ${X(e,Sr,e=>{let n=r.get(e.key),a=!e.ok&&G(e)&&(n?.lastOk??-1)>(i.get(e)??0)?n?.lastOkTry??0:0;return this.row(e,t,(n?.count??1)>1,a)})}
      </div>
      ${e.length?j:A`<div class="meta" style="padding:8px">${w(`No finished attempts`)}</div>`}`}shortStop(e){return e===`invalid_input`?Yr(`not_started`):q(e)}reason(e,t,n){let r=ui(e.hops),i=this.run||e.run_id||``,a=this.outcomes.get(e.key),o=e.stop===`invalid_input`&&a?pi({attempts:[e],cause:null},this.outcomes,i):``,s=o?rn(o):(!e.ok||!t)&&e.reason?J(e.reason,i):``,c=n?w(S`The task was done on attempt ${n}`):``;return!r&&!s&&!c?A`<span class="jdim">—</span>`:A`${r?A`<span class="nw" title=${w(`Model switch`)}>${r}</span><br />`:j}${s?A`${s}<br />`:j}${c?A`<span class="later">${c}</span>`:j}`}identity(e){let t=[...new Set([...(e.hops??[]).map(e=>e.credential),e.credential].filter(Boolean))];if(!t.length)return j;let n=(e.quota??[])[0],r=n?w(S`Usage at session start (account-wide): ${Da(n)}`):``,i=n&&t.length===1&&(n.credential??``)===t[0],a=n?i?Ta(n):Da(n):``;return A`<span class="sub" title=${[r,...t.map(ci)].filter(Boolean).join(`
`)||j}>${t.map(e=>si(e)).join(` → `)}${n?A` <span class="q">${a}</span>`:j}</span>`}spend(e){let t=e.usage,n=e.hops??[],r=n.length>1?n.map(e=>F(e.model||e.route||`—`,si(e.credential)||`—`,on(e.cost_usd),q(e.stop))).join(`
`):``;return A`<span class="num two">${t?A`<span>${R(t.input)} / ${R(t.output)}</span><span class="sub">${R(t.cache_read)} / ${R(t.cache_creation)}</span>`:A`<span class="jdim">—</span>`}</span>
      <span class="cost" title=${r||w(`Reported by the coding agent`)}>${on(e.cost_usd)}</span>`}row(e,t,r,i){let a=G(e),o=a&&xr(e),s=W(e),c=ui(e.hops),l=a?oi((e.rounds??1)-1):``,u=w(s?`Python task`:`Agent task`);return A`<div class=${`jrow${o?` bad`:``}${a?``:` notrun`}${s?` py`:` agent`}${this.fresh.has(Sr(e))?` fresh`:``}`} style=${is}
      @click=${()=>n(this,`ca-open-task`,s?{key:e.key,view:`output`}:{key:e.key})}>
      <span class="jmono" title=${P(e.ts,!0)}>${P(e.ts)}</span>
      <span class="jmono" title=${e.key}><span title=${u}><span aria-hidden="true">${s?`⚙`:`✦`}</span><span class="sr">${u}</span></span>
        ${I(e)}</span>
      <span class="jstop two j-${e.stop||`?`}" title=${e.stop||``}><span class="nw">${this.shortStop(e.stop)}</span>${r&&a||l?A`<span class="sub">${F(r&&a?ei(e.attempt):``,l)}</span>`:j}</span>
      <span class="jmono jdim two" title=${F(e.route,c)||j}>${a?A`<span>${[e.agent,e.model].filter(Boolean).join(` / `)||`—`}</span>${this.identity(e)}`:`—`}</span>
      ${this.spend(e)}
      <span class="num">${a?A`${N(e.wall_s)}<span class="jdur"><i class=${o?`bad`:s?``:`llm`}
            style="width:${Math.max(2,Math.round(100*(e.wall_s||0)/t))}%"></i></span>`:`—`}</span>
      <span class="jwhy" title=${e.reason||j}>${this.reason(e,a,i)}${sn([e])?A` <span class="unread nw" title=${w(S`Event types from the coding agent that this contraagent version does not recognize: ${sn([e])}`)}
            ><span aria-hidden="true">⚠</span> ${w(`Unrecognized events`)}</span
          >`:j}</span>
    </div>`}};U([V({attribute:!1})],as.prototype,`rows`,void 0),U([V({attribute:!1})],as.prototype,`fresh`,void 0),U([V()],as.prototype,`kind`,void 0),U([V()],as.prototype,`stop`,void 0),U([V()],as.prototype,`q`,void 0),U([V()],as.prototype,`run`,void 0),as=U([B(`ca-journal-table`),D()],as);var os=[`invalid`,`refused`,`failed`,`running`,`pending`,`valid`];function ss(e){let t=e?.tally,n=t?os.filter(e=>t[e]):[];return n.length?n.map(e=>A`<span class="ct-chip ${e}" title=${Ja(e)}>${qa(e)} <b>${t?.[e]}</b></span>`):A`<span class="meta">${w(`No checked files`)}</span>`}var cs=e=>e.split(`/`).slice(-2).join(`/`),ls=e=>I({kind:e.kind||e.key,unit:e.unit&&e.unit!==e.key?e.unit:``}),us=e=>e?os.indexOf(e):os.length,ds=class extends M{constructor(...e){super(...e),this.outputs=null,this.run=``,this.journal=[],this.plan=null,this.outcomes=new Map,this.open=new b(`contracts:open`),this.producerOf=e=>{for(let t of this.outputs?.contracts??[]){let n=(t.outputs??[]).find(t=>t.path===e);if(n)return{name:ls(t),written:!!n.file.exists,outcome:this.outcomes.get(t.key)?.outcome}}}}static{this.styles=[z,ho,k`
      :host { display: block; }
      .ct-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
      details.ct { border-top: 1px solid var(--line); }
      details.ct > summary { list-style: none; cursor: pointer; padding: 7px 4px; display: flex; align-items: center; gap: 10px; }
      details.ct > summary::-webkit-details-marker { display: none; }
      details.ct > summary::before { content: '▸'; color: var(--mut); width: 10px; transition: transform 0.15s; }
      details.ct[open] > summary::before { transform: rotate(90deg); }
      details.ct > summary:hover { background: var(--raise); border-radius: 8px; }
      .k-ic { margin-right: 0; }
      .ct-f { margin-left: auto; white-space: nowrap; }
      .ct-body { padding: 4px 10px 14px 24px; }
      .ct-links { margin-top: 10px; font-size: 12px; }
      .lead { margin: -4px 0 10px; }
      .one { display: flex; align-items: center; gap: 10px; padding: 7px 4px 7px 24px; border-top: 1px solid var(--line); flex-wrap: wrap; }
      .why { color: var(--fg2); font-size: 12px; }
    `]}render(){let e=this.outputs?.contracts??[];if(this.outcomes=this.plan?jr(this.journal,this.plan):new Map,!e.length)return A`<div class="blank"><span class="ic" aria-hidden="true">▣</span><b>${w(`No checked files`)}</b>
        <span>${w(`No task declares an OutputContract or an InputContract`)}</span></div>`;let t=e.flatMap(e=>(e.outputs??[]).map(t=>[e,t])).sort(([e,t],[n,r])=>us(t.status)-us(r.status)||e.key.localeCompare(n.key)),n=e.flatMap(e=>(e.inputs??[]).map(t=>[e,t]));return A`<div class="g12">
      <section class="panel c12">
        <h3 title=${w(`OutputContract`)}>${w(`Outputs`)}
          <span class="r">${w(`Files each task must write`)}</span></h3>
        <div class="ct-row">${ss(this.outputs)}</div>
        ${X(t,([e,t])=>`out|${e.key}|${t.path}`,([e,t])=>this.outRow(e,t))}
      </section>
      ${n.length?A`<section class="panel c12">
            <h3 title=${w(`InputContract`)}>${w(`Inputs`)}
              <span class="r">${w(`Files each task reads, checked when the task starts`)}</span></h3>
            ${X(n,([e,t])=>`in|${e.key}|${t.path}`,([e,t])=>this.inRow(e,t))}
          </section>`:j}
    </div>`}details(e,t,n){return A`<details class="ct" ?open=${this.open.has(e)}
      @toggle=${t=>this.open.set(e,t.target.open)}>
      <summary class="ct-sum">${t}</summary>
      <div class="ct-body">${n}</div>
    </details>`}link(e,t,r){return A`<a class="lnk" href="#" @click=${r=>{r.preventDefault(),n(this,`ca-open-task`,{key:e,view:t})}}>${r}</a>`}who(e){let t=W(e),n=w(t?`Python task`:`Agent task`);return A`<span class="k-ic ${t?``:`llm`}" title=${n}><span aria-hidden="true">${t?`⚙`:`✦`}</span><span class="sr">${n}</span></span>
      <b class="jmono" title=${e.key}>${ls(e)}</b>`}reasonOf(e){for(let t=this.journal.length-1;t>=0;t--){let n=this.journal[t];if(n?.key===e)return J(n.reason,this.run)}return``}outRow(e,t){if(t.status===`refused`)return A`<div class="one">
        <span class="ct-chip refused" title=${Ja(`refused`)}>${qa(`refused`)}</span>${this.who(e)}
        <span class="why">${fo(t,this.run,this.producerOf)}</span>
      </div>`;let n=t.file,r=t.status,i=t.rounds??0,a=t.errors??[],o=ls(e);return this.details(`out|${e.key}|${t.path}`,A`<span class="ct-chip ${r??``}" title=${r?Ja(r):``}>${r?qa(r):`—`}</span>
        ${i>1?A`<span class="meta" title=${Ya()}>${Xa(i,r===`valid`)}</span>`:j}
        ${this.who(e)}
        <span class="jmono jdim ct-path" title=${t.path}>${cs(t.path)}</span>
        ${r===`failed`&&this.reasonOf(e.key)?A`<span class="why">${this.reasonOf(e.key)}</span>`:j}
        <span class="meta ct-f">${n.exists?`${n.size??0} B`:r?j:w(`No file`)}</span>`,A`${po(t,`output`)}
        ${oo(t)}
        ${a.length?A`<h4>${w(`Errors`)}</h4><pre class="ct-err">${a.map(e=>J(e,this.run)).join(`
`)}</pre>`:j}
        <div class="ct-links">
          ${this.link(e.key,`output`,w(S`${o}: input and output`))}
          ${W(e)?j:A`<br />${this.link(e.key,`transcript`,w(S`${o}: transcript`))}`}
        </div>`)}inRow(e,t){let n=t.file,r=!!n.exists;return this.details(`in|${e.key}|${t.path}`,A`${Qa(t)}
        ${this.who(e)}
        <span class="jmono jdim ct-path" title=${t.path}>${cs(t.path)}</span>
        <span class="meta ct-f">${r?`${n.size??0} B`:w(`No file`)}</span>`,A`${po(t,`input`)}
        ${oo(t)}
        <div class="ct-links">${this.link(e.key,`input`,w(S`${ls(e)}: input`))}</div>`)}};U([V({attribute:!1})],ds.prototype,`outputs`,void 0),U([V()],ds.prototype,`run`,void 0),U([V({attribute:!1})],ds.prototype,`journal`,void 0),U([V({attribute:!1})],ds.prototype,`plan`,void 0),ds=U([B(`ca-contracts`),D()],ds);var fs=3e3,ps=class extends M{constructor(...e){super(...e),this.run=``,this.live=!1,this.journal=[],this.plan=null,this.selected=null,this.defs=[],this.defsRun=``,this.timer=null}static{this.styles=[z,k`
      :host { display: block; }
      .defs { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 14px; align-items: start; }
      .deflist { display: flex; flex-direction: column; gap: 6px; }
      .defitem { padding: 9px 12px; border-radius: 10px; background: var(--panel); border: 1px solid var(--line); cursor: pointer;
        display: flex; flex-direction: column; gap: 2px; }
      .defitem:hover { border-color: var(--line2); }
      .defitem.sel { border-color: var(--live); background: var(--live-a); }
      @media (max-width: 900px) {
        .defs { grid-template-columns: 1fr; }
      }
    `]}disconnectedCallback(){super.disconnectedCallback(),this.clearTimer(),this.defsRun=``}connectedCallback(){super.connectedCallback(),this.run&&this.defsRun!==this.run&&this.load()}willUpdate(e){(e.has(`run`)||e.has(`client`))&&this.run&&this.client&&this.defsRun!==this.run&&(this.defs=[],this.load())}updated(){let e=new Set(this.tasks().filter(e=>!W(e)&&(e.tries.length||e.outcome===`running`)).map(e=>e.kind)).size;this.live&&this.defsRun===this.run&&this.defs.length<e&&!this.timer&&(this.timer=setTimeout(()=>{this.timer=null,this.load()},fs))}tasks(){return[...jr(this.journal,this.plan??{nodes:[],groups:[]}).values()]}clearTimer(){this.timer&&clearTimeout(this.timer),this.timer=null}async load(){if(!this.client||!this.run)return;let e=this.run;this.defsRun=e;let t=[];try{t=await this.client.definitions(e)}catch{t=[]}e===this.run&&(this.defs=t)}render(){let e=this.defs,t=this.tasks(),r=[...new Set(t.filter(e=>W(e)).map(e=>e.kind))].filter(t=>!e.some(e=>e.kind===t));if(!e.length&&!r.length)return A`<div class="blank"><span class="ic" aria-hidden="true">⌘</span><b>${this.live?w(`No definitions yet`):w(`No definitions`)}</b></div>`;let i=this.selected!==null&&r.includes(this.selected)?this.selected:null,a=i?void 0:e.find(e=>e.kind===this.selected)??e.find(e=>e.plugin)??e[0],o=i??a?.kind??r[0]??``,s=e=>{let n=t.filter(t=>t.kind===e),r=n.length,i=n.reduce((e,t)=>e+t.tries.length,0);return F(w(r===1?`1 task`:S`${r} tasks`),w(i===1?`1 attempt`:S`${i} attempts`))};return A`<div class="defs">
      <div class="deflist">
        ${X(e,e=>e.kind,e=>A`<div class="defitem ${e.kind===o?`sel`:``}" @click=${()=>n(this,`ca-navigate`,{def:e.kind})}>
            <b class="jmono">${e.kind}</b>
            <span class="meta words">${_o(F(e.executor===`python`?`Python`:e.role?w(S`Role ${e.role}`):w(`No role`),s(e.kind)))}</span>
          </div>`)}
        ${X(r,e=>e,e=>A`<div class="defitem ${e===o?`sel`:``}" @click=${()=>n(this,`ca-navigate`,{def:e})}>
            <b class="jmono">${e}</b>
            <span class="meta words">${_o(F(`Python`,s(e)))}</span>
          </div>`)}
      </div>
      <section class="panel">
        ${a?A`<h3 title=${w(`As recorded when its first task started (definitions/<kind>.json)`)}>
                ${a.kind}<span class="r">${a.executor===`python`?w(`Python task`):a.plugin?w(S`Plugin ${a.name||``}`):w(`Defined in Python code`)}</span>
              </h3>
              <ca-definition .definition=${a} memory="definition:${a.kind}"></ca-definition>`:A`<h3>${o}<span class="r">${w(`Python task`)}</span></h3>
              <ca-definition .definition=${null}></ca-definition>`}
      </section>
    </div>`}};U([V({attribute:!1})],ps.prototype,`client`,void 0),U([V()],ps.prototype,`run`,void 0),U([V({type:Boolean})],ps.prototype,`live`,void 0),U([V({attribute:!1})],ps.prototype,`journal`,void 0),U([V({attribute:!1})],ps.prototype,`plan`,void 0),U([V({attribute:!1})],ps.prototype,`selected`,void 0),U([H()],ps.prototype,`defs`,void 0),ps=U([B(`ca-definitions`),D()],ps);var ms=class extends M{constructor(...e){super(...e),this.procs=null}static{this.styles=[z,k`
      :host { display: block; }
      .cmd { word-break: break-all; }
    `]}render(){let e=this.procs;if(!e?.alive)return A`<div class="blank"><span class="ic" aria-hidden="true">⚙</span><b>${F(w(`No processes`),w(`run not running`))}</b></div>`;let t=e.python_tasks;return A`<div class="g12">
      <section class="panel c12">
        <h3 title=${w(`One per task (Backend.run)`)}>${w(`Agent sessions running`)} <span class="r">${e.launches.length}</span></h3>
        ${e.launches.length?X(e.launches,e=>e.key,e=>A`<div class="fl" @click=${()=>n(this,`ca-open-task`,{key:e.key})}>
                <b class="jmono">${I(e)}</b>
                <span class="meta">${F(w(S`PID ${e.pid}`),w(S`Model ${e.model||`—`}`),e.role?w(S`Role ${e.role}`):``)} |
                  <ca-elapsed .since=${In.at(`c:${e.key}`,e.age_s)}></ca-elapsed></span>
                <div class="meta mono cmd">${(e.full_cmd||w(`In the pipeline process`)).slice(0,400)}</div>
              </div>`):A`<div class="meta">${w(`No agent sessions`)}</div>`}
      </section>
      ${t.length?A`<section class="panel c12">
            <h3 title=${w(`Functions in the pipeline process`)}>${w(`Python tasks running`)} <span class="r">${t.length}</span></h3>
            ${X(t,e=>e.key,e=>A`<div class="fl">
                <b class="jmono">${I(e)}</b>
                <span class="meta">${w(S`PID ${e.pid}`)} | <ca-elapsed .since=${In.at(`p:${e.key}`,e.age_s)}></ca-elapsed></span>
              </div>`)}
          </section>`:j}
      <section class="panel c12"><h3>${w(`Process tree`)}</h3><ca-proc-tree .procs=${e}></ca-proc-tree></section>
    </div>`}};U([V({attribute:!1})],ms.prototype,`procs`,void 0),ms=U([B(`ca-procs-view`),D()],ms);var hs=class extends M{constructor(...e){super(...e),this.name=``}static{this.styles=[z,k`
      :host { display: block; }
      .tab-ic { opacity: 1; margin-right: 6px; font-size: 12px; }
      .desc { margin: -4px 0 12px; }
    `]}render(){if(this.data===void 0)return this.panel?A`<div class="blank"><span class="ic" aria-hidden="true">…</span>${w(`Loading…`)}</div>`:A`<div class="blank"><span class="ic" aria-hidden="true">▤</span>${w(S`No custom view named ${this.name}`)}</div>`;let e=this.panel;return A`<section class="panel">
      <h3><span class="tab-ic" aria-hidden="true">${e?.icon||`▤`}</span>${e?.title||this.name}
        <span class="r">${w(`Custom view`)}</span></h3>
      ${e?.description?A`<div class="meta desc">${e.description}</div>`:j}
      <ca-json-tree .value=${this.data}></ca-json-tree>
    </section>`}};U([V()],hs.prototype,`name`,void 0),U([V({attribute:!1})],hs.prototype,`panel`,void 0),U([V({attribute:!1})],hs.prototype,`data`,void 0),hs=U([B(`ca-panel-view`),D()],hs);function gs(e,t){return t>1?e.fixupNo?w(S`Attempt ${e.tryNo} | correction ${e.fixupNo}`):e.hopNo?w(S`Attempt ${e.tryNo} | model switch`):ei(e.tryNo-1):e.fixupNo?w(S`Correction ${e.fixupNo}`):e.hopNo?w(`Model switch`):ei(0)}function _s(e){return e.fixupNo?w(`same agent session, after failed checks`):e.hopNo?w(`new agent session on the next model`):e.tryNo>1?w(S`new agent session after attempt ${e.tryNo-1} failed`):w(`first agent session`)}function vs(e){let t=e.model||w(`model`);return e.switchedTo?w(S`${t}: ${q(e.switchedStop)}; switched to ${e.switchedTo}`):w(S`${t}: ${q(e.switchedStop)}; switched to the next model`)}function ys(e,t){switch(e.result){case`ok`:return[`✓`,w(`passed`),w(`Output passed checks`)];case`rejected`:return[`✕`,w(`failed checks`),w(`Output failed checks`)];case`switched`:return[`✕`,q(e.switchedStop),vs(e)];case`failed`:return[`✕`,w(`failed`),J(e.row?.reason,t)||q(e.row?.stop)];default:return[``,``,``]}}var bs={claude:`Claude Code`,omp:`omp`,codex:`Codex`,opencode:`opencode`,gemini:`Gemini CLI`};function xs(e){let t=String(e||``).split(`/`).pop()??``;return bs[t]??t}var Ss=(e,t)=>{let n=e.indexOf(t);return n>=0?e[n+1]??``:``};function Cs(e){let t=e.argv,n=/TELEMETRY [^\n]*role=([\w:-]+)/.exec(e.prompt||``)?.[1];return{agent:xs(t[0]),model:Ss(t,`--model`)||Ss(t,`-m`),role:n&&n!==`-`?n:``}}var ws=()=>({rounds:[],tools:new Map,next:0}),Ts=/session init:.*?model=([\w.\-:]+)/;function Es(e){return`i${e.next++}`}function Ds(e,t){let n={id:`r${e.rounds.length}`,launch:t,who:t?Cs(t):null,items:[]};return e.rounds.push(n),n}function Os(e){return e.rounds[e.rounds.length-1]??Ds(e,null)}function ks(e,t){t?e.name=t:e.name||=`tool`,e.icon=(e.name.split(/[_:]/).pop()??``).toLowerCase()}function As(e,t,n){let r=n?e.tools.get(n):void 0;return r||(r={kind:`tool`,id:n?`call:${n}`:Es(e),call:n,name:``,icon:``,preview:``,intent:``,cmd:``,webQuery:``,webFetch:``,out:null,status:`run`},n&&e.tools.set(n,r),t.items.push(r)),r}function js(e,t){let n=0;for(let r of t){let t=Xn(r);if(!t)continue;if(t.type===`launch`){Ds(e,t),n++;continue}let i=Os(e);switch(t.type){case`message_start`:case`message_end`:if(t.role!==`user`||!t.text)continue;i.items.push({kind:`prompt`,id:Es(e),text:t.text});break;case`turn_end`:if(!t.thinking)continue;i.items.push({kind:`summary`,id:Es(e),text:t.thinking});break;case`acall`:case`tool_execution_start`:case`tool_execution_update`:{let n=As(e,i,t.call);n.out===null?(ks(n,t.tool),n.preview=an(t.cmd),n.intent=t.intent||``,n.cmd=t.cmd||n.cmd,t.web_query&&(n.webQuery=t.web_query),t.web_fetch&&(n.webFetch=t.web_fetch)):!n.preview&&t.cmd&&(n.preview=an(t.cmd));break}case`aresult`:case`tool_execution_end`:{let n=As(e,i,t.call);if(n.out!==null&&!t.out)break;ks(n,t.tool),n.status=t.err?`err`:`ok`,!n.preview&&n.cmd&&(n.preview=an(n.cmd)),n.out=t.out||`(no output)`;break}case`message_update`:{if(!t.delta)continue;let n=i.items[i.items.length-1];n?.kind===`assistant`?n.raw+=t.delta:i.items.push({kind:`assistant`,id:Es(e),raw:t.delta});break}case`auto_retry_start`:i.items.push({kind:`retry`,id:Es(e),err:t.err??``});break;case`notice`:{let n=Ts.exec(t.text||``)?.[1];n&&(i.who??={agent:``,model:``,role:``},i.who.model||(i.who.model=n)),i.items.push({kind:`notice`,id:Es(e),text:(t.text||``).replace(/\s+/g,` `).trim()});break}}n++}return n}var Ms=`The output file(s) you wrote do not pass their checks.`;function Ns(e){let t=[],n=!1;for(let r of(e||``).split(`
`))/^Errors:\s*$/.test(r)?n=!0:n&&r.startsWith(`- `)?t.push(r.slice(2)):n&&r.trim()&&!r.startsWith(`- `)&&(n=!1);return t}var Ps=e=>!!e&&(e.prompt||``).startsWith(Ms);function Fs(e,t){let n=new Map(t.map(e=>[(e.attempt??0)+1,e])),r=[],i=0,a=0,o=0;return e.forEach((e,t)=>{let s=n.get(i)?.hops?.length??1;t>0&&Ps(e)?a++:t>0&&o+1<s?(o++,a=0):(i++,o=0,a=0);let c=n.get(i)?.hops?.[o],l=c?.model||c?.route||``,u=a?`fixup`:o?`switch`:`try`;r.push({kind:u,tryNo:i,fixupNo:a,hopNo:o,model:l,result:null,rejectedWith:[],switchedStop:``,switchedTo:``,row:null})}),r.forEach((t,i)=>{let a=r[i+1];if(a&&a.tryNo===t.tryNo&&a.hopNo!==t.hopNo){t.result=`switched`,t.switchedStop=n.get(t.tryNo)?.hops?.[t.hopNo]?.stop??``,t.switchedTo=a.model;return}if(a&&a.tryNo===t.tryNo){t.result=`rejected`,t.rejectedWith=Ns(e[i+1]?.prompt);return}let o=n.get(t.tryNo)??null;t.row=o,t.result=o?o.ok?`ok`:`failed`:null}),r}function Is(e){let t=/\[([\w.-]+)\]\s*(.*)$/.exec(e);return t?`${t[1]}: ${t[2]}`:e}var Ls=20,Rs=/\{\s*"title"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"url"\s*:\s*"(https?:\/\/[^"\s]+)"/g,zs=/^\s*\[\d+\]\s+(.+)\n\s*(https?:\/\/\S+)/gm,Bs=/https?:\/\/[^\s"'<>)\]]+/g;function Vs(e){let t=e??``,n=[],r=new Set,i=(e,t)=>{r.has(t)||n.length>=Ls||(r.add(t),n.push({title:e.trim()||t,url:t}))};for(let e of t.matchAll(Rs)){let t=e[1]??``;try{t=JSON.parse(`"${t}"`)}catch{}i(t,e[2]??``)}if(!n.length)for(let e of t.matchAll(zs))i(e[1]??``,e[2]??``);if(!n.length)for(let e of t.matchAll(Bs))i(``,e[0].replace(/[.,;:!?]+$/,``));return n}function Hs(e){return e?A`${e.agent?A`<span class="who agent" title=${w(`The CLI that ran the task (claude, omp)`)}
        ><span class="who-l">${w(`coding agent`)}</span>${e.agent}</span
      >`:j}${e.model?A`<span class="who model" title=${w(`The language model the coding agent used`)}
        ><span class="who-l">${w(`model`)}</span>${e.model}</span
      >`:j}${e.role?A`<span class="who role" title=${w(`The agent definition the coding agent ran as (agents/<role>.md)`)}
        ><span class="who-l">${w(`role`)}</span>${e.role}</span
      >`:j}`:A``}var Us=k`
  .who { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; font-weight: 600; padding: 2px 9px;
    border-radius: 7px; border: 1px solid var(--line2); white-space: nowrap; }
  .who-l { font-size: 10px; font-weight: 400; opacity: 0.75; font-family: var(--sans); }
  .who.agent { color: var(--live); border-color: rgba(34, 211, 238, 0.4); background: var(--live-a); }
  .who.model { color: var(--llm); border-color: rgba(167, 139, 250, 0.45); background: var(--llm-a); font-family: var(--mono); }
  .who.role { color: var(--fg2); font-family: var(--mono); font-weight: 500; }
`,Ws=60,Gs=1200,Ks=4e3,qs=3e3,Js=4e3;function Ys(e){try{return new URL(e).host}catch{return``}}var Q=class extends M{constructor(...e){super(...e),this.events=null,this.run=``,this.stream=null,this.baseUrl=``,this.client=null,this.live=!1,this.round=null,this.rows=[],this.mode=`full`,this.version=0,this.behind=0,this.bulk=!0,this.unseen=0,this.pinned=null,this.revealed=``,this.revealPending=!1,this.model=ws(),this.close=null,this.loaded=``,this.token=0,this.first=!0,this.stick=!0,this.restored=!1,this.lastTop=0,this.lastShown=-1,this.lastSent=``,this.openCards=new x(`transcript::open`),this.folds=new Set,this.openPrompts=new Set,this.mdCache=new WeakMap}static{this.styles=[z,Tn,Us,k`
      :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
      :host([mode='none']) { display: none; }
      :host([mode='tabs']) { flex: none; }
      :host([mode='tabs']) .scroller, :host([mode='tabs']) .newpill { display: none; }

      .rounds { flex: none; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 0 0 10px; padding-left: 2px; }
      .rounds-lbl { color: var(--mut); font-size: 11.5px; font-weight: 600; margin-right: 4px; cursor: help; }
      .stab { padding: 3px 11px; border: 1px solid var(--line); border-radius: 999px; background: var(--card); color: var(--mut);
        cursor: pointer; font-size: 12px; display: inline-flex; align-items: center; }
      .stab:hover { border-color: var(--info); }
      .stab.sel { background: var(--live-a); border-color: var(--live); color: var(--fg); }
      .stab-m { font-family: var(--mono); font-size: 10.5px; color: var(--llm); margin-left: 4px; }
      .stab .dot { width: 6px; height: 6px; margin-left: 4px; }
      .stab .mk { margin-right: 4px; }
      .stab .mk.ok { color: var(--ok); }
      .stab .mk.bad { color: var(--err); }
      .verdict { margin: 6px 10px 4px 41px; padding: 7px 11px; border-radius: 10px; border: 1px solid; font-size: 12px; }
      .verdict.rejected { border-color: rgba(251, 191, 36, 0.4); background: var(--warn-a); color: var(--fg); }
      .verdict.failed { border-color: rgba(248, 113, 113, 0.45); background: var(--err-a); color: var(--fg); }
      .verdict b { display: block; margin-bottom: 2px; }
      .verdict ul { margin: 2px 0 0; padding-left: 18px; font-family: var(--mono); font-size: 11.5px; }

      .scroller { flex: 1 1 auto; min-height: 0; overflow: auto; border: 1px solid var(--line); border-radius: 14px;
        background: linear-gradient(180deg, rgba(15, 23, 36, 0.85), rgba(9, 14, 22, 0.9)); padding: 4px 2px 8px; font-size: 12.5px; }
      .back { margin: 6px 10px; background: var(--raise); border: 1px solid var(--line2); border-radius: 8px; padding: 3px 10px; cursor: pointer; color: var(--fg2); }
      .back:hover { border-color: var(--live); }

      .inv-body { display: flex; flex-direction: column; gap: 10px; }
      .inv-head { border: 1px solid rgba(34, 211, 238, 0.25); border-radius: 12px; background: rgba(34, 211, 238, 0.05); padding: 8px 10px; margin: 4px 8px 6px; }
      .inv-who { display: flex; flex-wrap: wrap; gap: 6px; }
      .inv-cmdbox { margin-top: 6px; }
      .inv-cmdbox summary, .inv-prompt summary { cursor: pointer; font-size: 11px; color: var(--mut); }
      .inv-prompt summary { font-size: 11.5px; }
      .inv-prompt summary:hover { color: var(--info); }
      .inv-cmd { font-family: var(--mono); font-size: 11.5px; white-space: pre-wrap; word-break: break-all; margin: 4px 0 6px; max-height: 160px; overflow: auto; color: var(--fg); }
      .inv-ptext { margin-top: 6px; max-height: 360px; overflow: auto; }

      .msg { display: flex; gap: 9px; padding: 3px 10px; }
      .av { width: 22px; height: 22px; flex: 0 0 22px; border-radius: 7px; line-height: 22px; font-size: 11px; text-align: center; font-weight: 700; }
      .av-a { background: linear-gradient(135deg, #7c3aed, #a78bfa); box-shadow: 0 4px 12px rgba(124, 58, 237, 0.35); color: #fff; }
      .av-l { background: var(--raise); color: var(--live); }
      .av-t { background: var(--raise); color: var(--mut); }
      .bd { flex: 1; min-width: 0; background: rgba(255, 255, 255, 0.025); border: 1px solid var(--line); border-radius: 3px 10px 10px 10px; padding: 5px 10px; }
      .hd { font-size: 11px; font-weight: 600; color: var(--mut); margin-bottom: 1px; }
      .tx { color: var(--fg); line-height: 1.5; word-break: break-word; }
      .tx pre, .tx code { white-space: pre-wrap; }
      .tx pre { margin: 0 0 4px; }

      .toolcard, .typing { margin-left: 41px; margin-right: 10px; }
      .toolcard { border: 1px solid var(--line); border-left: 3px solid var(--line2); border-radius: 10px; margin-top: 3px; margin-bottom: 3px;
        overflow: hidden; background: rgba(0, 0, 0, 0.18); transition: border-color 0.3s; }
      .toolcard.run { border-left-color: var(--live); }
      .toolcard.ok { border-left-color: rgba(52, 211, 153, 0.6); }
      .toolcard.err { border-left-color: var(--err); }
      .th { display: flex; gap: 9px; align-items: baseline; padding: 4px 9px; cursor: pointer; }
      .th:hover { background: rgba(255, 255, 255, 0.03); }
      .tn { font-family: var(--mono); font-weight: 600; flex: none; display: inline-flex; align-items: center; }
      .tn::before { content: '⚒'; display: inline-grid; place-items: center; width: 20px; height: 20px; margin-right: 7px;
        border-radius: 6px; background: var(--raise); color: var(--fg2); font-size: 11px; }
      .toolcard[data-tool='bash'] .tn::before { content: '❯'; color: var(--ok); }
      .toolcard[data-tool='read'] .tn::before { content: '▤'; color: var(--info); }
      .toolcard[data-tool='grep'] .tn::before, .toolcard[data-tool='glob'] .tn::before { content: '⌕'; color: var(--warn); }
      .toolcard[data-tool='edit'] .tn::before, .toolcard[data-tool='write'] .tn::before { content: '✎'; color: var(--llm); }
      .toolcard[data-tool='task'] .tn::before, .toolcard[data-tool='agent'] .tn::before { content: '✦'; color: var(--llm); }
      .toolcard[data-tool='web-search'] .tn::before { content: '◍'; color: var(--info); }
      .toolcard[data-tool='web-fetch'] .tn::before { content: '⇣'; color: var(--info); }
      .toolcard.revealed { box-shadow: 0 0 0 1px var(--live); }
      .tp { font-family: var(--mono); font-size: 11.5px; color: var(--fg); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .ti { color: var(--mut); font-size: 11px; flex: none; max-width: 35%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .st-run, .st-ok, .st-err, .st-int { flex: none; white-space: nowrap; }
      .st-run { color: var(--live); display: inline-flex; align-items: center; gap: 6px; }
      .st-ok { color: var(--ok); }
      .st-err { color: var(--err); }
      .st-int { color: var(--warn); }
      .pdot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--live); animation: breathe 1.8s ease-in-out infinite; }
      .tb { padding: 6px 9px; border-top: 1px solid var(--line); background: rgba(0, 0, 0, 0.25); }
      .tb pre { white-space: pre-wrap; word-break: break-word; margin: 4px 0; font-family: var(--mono); font-size: 12px; }
      .fold { max-height: 220px; overflow: hidden; position: relative; }
      .fold.open { max-height: none; }
      .foldbtn { cursor: pointer; color: var(--info); font-size: 11px; background: none; border: 0; padding: 0; font-family: inherit; }
      .wq { font-size: 12px; margin: 2px 0 6px; }
      .wq b { font-family: var(--mono); font-weight: 600; }
      .wl { color: var(--mut); font-size: 11px; margin-right: 6px; }
      .links { margin: 0 0 6px; padding-left: 30px; font-size: 12px; }
      .links li { margin: 2px 0; overflow-wrap: anywhere; }
      .links a { color: var(--info); text-decoration: none; }
      .links a:hover { text-decoration: underline; }
      .rawfold > summary { cursor: pointer; color: var(--mut); font-size: 11px; }
      .plink { color: var(--info); text-decoration: none; font-family: var(--mono); overflow-wrap: anywhere; }
      .plink:hover { text-decoration: underline; }
      .host { color: var(--mut); font-family: var(--mono); font-size: 11px; margin-left: 6px; }

      .sysline { display: flex; gap: 8px; align-items: baseline; padding: 2px 10px 2px 41px; font-size: 11px; color: var(--mut); font-family: var(--mono); }
      .sysline .tx { color: var(--mut); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .typing { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
      .typing .av { width: 26px; height: 26px; flex: 0 0 26px; border-radius: 9px; display: grid; place-items: center; font-size: 12px; }
      .dots { display: inline-flex; gap: 4px; padding: 8px 12px; border-radius: 12px; background: var(--llm-a); }
      .dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--llm); animation: bounce 1.2s infinite ease-in-out; }
      .dots i:nth-child(2) { animation-delay: 0.15s; }
      .dots i:nth-child(3) { animation-delay: 0.3s; }
      .scroller:not(.bulk) .msg, .scroller:not(.bulk) .toolcard { animation: enter 0.35s var(--ease) both; }

      .newpill { position: absolute; left: 50%; bottom: 26px; transform: translateX(-50%); z-index: 5; cursor: pointer; padding: 6px 14px;
        border-radius: 999px; border: 1px solid rgba(34, 211, 238, 0.5); background: rgba(8, 20, 32, 0.92); color: var(--live);
        font-size: 12px; font-weight: 600; box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5); backdrop-filter: blur(6px); animation: toast-in 0.3s var(--ease) both; }
      .newpill:hover { background: var(--live-a); }
    `]}get source(){return this.events?`static`:this.run&&this.stream?`${this.run}\n${this.stream}`:``}get memoryId(){return`transcript:${this.run}/${this.stream??``}`}disconnectedCallback(){super.disconnectedCallback(),this.close?.(),this.close=null,this.loaded=``}connectedCallback(){super.connectedCallback(),this.hasUpdated&&this.requestUpdate()}willUpdate(e){let t=this.source;(e.has(`events`)||t!==this.loaded)&&this.load(t)}load(e){if(this.close?.(),this.close=null,this.loaded=e,this.token++,this.model=ws(),this.first=!0,this.behind=0,this.bulk=!0,this.unseen=0,this.pinned=null,this.stick=!0,this.restored=!1,this.lastShown=-1,this.folds.clear(),this.openPrompts.clear(),this.openCards=new x(`${this.memoryId}:open`),this.events){js(this.model,this.events),this.version++,this.afterFirstPage(this.token);return}if(!e||!this.stream)return;let t=this.token;this.close=_r(this.run,this.stream,{message:e=>this.onPage(e,t)},{baseUrl:this.baseUrl})}onPage(e,t){if(t!==this.token)return;this.first&&e.behind&&(this.behind=e.behind);let n=this.model.rounds.length,r=js(this.model,e.events);if(n&&this.model.rounds.length>n&&this.round===null&&this.pinned===null&&!this.stick&&!this.bulk&&(this.pinned=n),this.version++,this.first){this.first=!1,this.afterFirstPage(t);return}this.updateComplete.then(()=>{t===this.token&&(this.stick&&this.onLiveRound()?this.toBottom():this.unseen+=r)})}async afterFirstPage(e){if(await this.updateComplete,e!==this.token)return;let t=this.stream?te(`${this.memoryId}:scroll`):void 0,n=this.scroller;if(!t||t.stick||!n)this.stick=!0,this.toBottom();else{this.stick=!1;let r=performance.now()+Js;await new Promise(i=>{let a=()=>{let o=n.scrollHeight-n.clientHeight;n.scrollTop=Math.min(t.top,o),o>=t.top||performance.now()>r||e!==this.token?i():requestAnimationFrame(a)};a()}),this.lastTop=n.scrollTop}this.restored=!0,requestAnimationFrame(()=>{e===this.token&&(this.bulk=!1)})}shownIndex(){let e=this.model.rounds.length;if(!e)return-1;let t=this.round===null?this.pinned??e-1:this.round-1;return Math.max(0,Math.min(e-1,t))}onLiveRound(){let e=this.model.rounds.length;return e<2||this.shownIndex()===e-1}toBottom(e=!1){let t=this.scroller;t&&(e?t.scrollTo({top:t.scrollHeight,behavior:`smooth`}):t.scrollTop=t.scrollHeight)}onScroll(){let e=this.scroller;e&&e.clientHeight&&(this.stick=e.scrollHeight-e.scrollTop-e.clientHeight<Ws,this.lastTop=e.scrollTop,this.stick&&this.onLiveRound()&&(this.unseen=0),this.restored&&this.stream&&y(`${this.memoryId}:scroll`,{stick:this.stick,top:Math.round(e.scrollTop)}))}updated(e){let t=this.shownIndex();if(t!==this.lastShown){let e=this.lastShown;this.lastShown=t,e!==-1&&this.restored&&this.toBottom()}let n=e.get(`mode`);n&&n!==`full`&&this.mode===`full`&&this.scroller&&(this.stick?this.toBottom():this.scroller.scrollTop=this.lastTop);let r=`${this.version}|${t}|${this.model.rounds.length}|${this.rows.length}`;if(r!==this.lastSent){this.lastSent=r;let e={launches:this.model.rounds.map(e=>e.launch),shown:t,rounds:this.infos()};this.dispatchEvent(new CustomEvent(`rounds-changed`,{detail:e}))}if(this.revealPending){let e=this.renderRoot.querySelector(`[data-card="${CSS.escape(this.revealed)}"]`);e&&this.mode===`full`&&(this.revealPending=!1,this.stick=!1,e.scrollIntoView({block:`center`}))}}infos(){return Fs(this.model.rounds.map(e=>e.launch),this.rows)}pickRound(e){this.pinned=null;let t=this.model.rounds.length-1;n(this,`ca-navigate`,{round:e===t?null:e+1})}jumpToLive(){let e=this.model.rounds.length;e>1&&this.shownIndex()!==e-1&&(this.pinned=null,this.round!==null&&n(this,`ca-navigate`,{round:null})),this.stick=!0,this.unseen=0,this.updateComplete.then(()=>this.toBottom(!0))}async loadEarlier(){let{run:e,stream:t}=this;if(!t)return;let n=this.token,r=Math.max(0,this.behind-qs);this.behind=0;let i=await(this.client??fr({baseUrl:this.baseUrl})).stream(e,t,r);n===this.token&&(this.model=ws(),this.lastShown=-1,js(this.model,i.events),this.version++)}render(){let e=this.model.rounds,t=this.shownIndex(),n=e[t],r=this.onLiveRound();return A`${this.renderRounds(e,t)}
      <div class="scroller ${this.bulk?`bulk`:``}" @scroll=${()=>this.onScroll()}>
        ${this.behind?A`<div class="meta"><button type="button" class="back" @click=${()=>void this.loadEarlier()}>
              ${this.behind===1?w(`Show 1 earlier line`):w(S`Show ${this.behind} earlier lines`)}</button></div>`:j}
        ${n?this.renderRound(n,t===e.length-1,this.infos()[t]):j}
        ${!n&&this.live?this.typing():j}
      </div>
      ${this.unseen?A`<button type="button" class="newpill" @click=${()=>this.jumpToLive()}>
            ${this.unseen===1?w(r?`Show 1 new event`:`Show 1 new event in the running agent session`):w(r?S`Show ${this.unseen} new events`:S`Show ${this.unseen} new events in the running agent session`)}</button>`:j}`}renderRounds(e,t){if(e.length<2)return j;let n=e.length-1,r=this.infos(),i=r[r.length-1]?.tryNo??1;return A`<div class="rounds" role="group" aria-label=${w(`Agent sessions`)}>
      <span class="rounds-lbl"
        title=${[w(`Attempt: a new agent session`),w(`Correction: the same agent session after failed checks`),w(`Model switch: a new agent session on the next model`)].join(`
`)}
        >${w(`Agent sessions`)}</span>
      ${e.map((e,a)=>{let o=r[a],[s,c,l]=o?ys(o,this.run):[``,``,``];return A`<button type="button" class="stab ${a===t?`sel`:``}" title=${l||j} aria-pressed=${a===t}
          @click=${()=>this.pickRound(a)}>
          ${s?A`<span class="mk ${s===`✓`?`ok`:`bad`}" aria-hidden="true">${s}</span><span class="sr">${c}</span>`:j}${o?gs(o,i):String(a+1)}
          ${e.who?.model?A` <span class="stab-m">${e.who.model.replace(/^claude-/,``)}</span>`:j}
          ${a===n&&this.live&&this.close?A`<span class="dot live"></span>`:j}
        </button>`})}
    </div>`}renderRound(e,t,n){return A`<div class="inv-body">
      ${e.launch?this.renderHead(e,e.launch):j}
      ${X(e.items,e=>e.id,e=>this.renderItem(e))}
      ${t&&this.live?this.typing():j}
      ${n?this.renderVerdict(n):j}
    </div>`}renderVerdict(e){if(e.result===`rejected`)return A`<div class="verdict rejected">
        <b>${w(`Output failed checks`)}</b>
        ${e.rejectedWith.length?A`<ul>${e.rejectedWith.map(e=>A`<li>${J(e,this.run)}</li>`)}</ul>`:A`<span class="meta">${w(`The errors are in the correction prompt`)}</span>`}
      </div>`;if(e.result===`switched`)return A`<div class="verdict failed">
        <b>${vs(e)}</b>
      </div>`;if(e.result===`failed`&&e.row){let t=J(e.row.reason,this.run)||q(e.row.stop);return A`<div class="verdict failed"><b>${w(S`Attempt ${e.tryNo} failed: ${t}`)}</b></div>`}return j}renderHead(e,t){let n=t.prompt||``,r=t.prompt_truncated||0,i=this.openPrompts.has(e.id);return A`<div class="inv-head">
      <div class="inv-who">${Hs(e.who)}</div>
      <details class="inv-cmdbox"><summary>${w(`Command line`)}</summary><pre class="inv-cmd"><code>${t.argv.join(` `)}</code></pre></details>
      <details class="inv-prompt" ?open=${i}
        @toggle=${t=>{let n=t.target.open;n!==this.openPrompts.has(e.id)&&(n?this.openPrompts.add(e.id):this.openPrompts.delete(e.id),this.requestUpdate())}}>
        <summary>${w(r?S`Prompt (${n.length} characters; ${r} characters not saved)`:S`Prompt (${n.length} characters)`)}</summary>
        ${i?A`<div class="inv-ptext"><ca-markdown .text=${n+(r?`\n\n${w(S`(${r} characters not saved)`)}`:``)}></ca-markdown></div>`:j}
      </details>
    </div>`}mdOf(e,t){let n=this.mdCache.get(e);if(n?.raw===t)return n.html;let r=bn(t);return this.mdCache.set(e,{raw:t,html:r}),r}bubble(e,t,n,r,i){return A`<div class="msg" title=${i??j}>
      <div class="av ${t}">${e}</div>
      <div class="bd"><div class="hd">${n}</div>${r}</div>
    </div>`}renderItem(e){switch(e.kind){case`prompt`:return this.bubble(`▸`,`av-l`,w(`Prompt`),A`<div class="tx meta">${w(S`${e.text.length} characters`)}</div>`,e.text.slice(0,600));case`assistant`:return this.bubble(`A`,`av-a`,w(`Assistant`),A`<div class="tx">${Wn(this.mdOf(e,e.raw))}</div>`);case`summary`:return this.bubble(`✦`,`av-t`,w(`Reasoning`),A`<div class="tx">${Wn(this.mdOf(e,e.text))}</div>`);case`retry`:return A`<div class="msg"><div class="av av-t" aria-hidden="true">↻</div><div class="bd"><div class="hd">${w(`API request sent again`)}</div>${e.err?A`<div class="tx meta">${e.err}</div>`:j}</div></div>`;case`notice`:return A`<div class="sysline"><span aria-hidden="true">⚙</span><span class="tx">${e.text}</span></div>`;case`tool`:return this.toolCard(e)}}toolCard(e){let t=this.openCards.has(e.id),n=e.webQuery?Vs(e.out):[],r=e.status===`ok`?A`<span class="st-ok"><span aria-hidden="true">✓</span> ${w(`done`)}</span>`:e.status===`err`?A`<span class="st-err"><span aria-hidden="true">✕</span> ${w(`failed`)}</span>`:this.live?A`<span class="st-run"><i class="pdot"></i>${w(`running`)}</span>`:A`<span class="st-int" title=${w(`The run ended before the tool call returned`)}><span aria-hidden="true">◌</span> ${w(`interrupted`)}</span>`,i=e.webQuery?`web-search`:e.webFetch?`web-fetch`:e.icon;return A`<div class="toolcard ${e.status} ${this.revealed===e.id?`revealed`:``}" data-tool=${i} data-card=${e.id}>
      <div class="th" @click=${()=>{this.openCards.set(e.id,!t),this.requestUpdate()}}>
        <span class="tn">${e.name||w(`tool`)}</span><span class="tp">${e.preview}</span><span class="ti"
          >${n.length===1?w(`1 result`):n.length?w(S`${n.length} results`):e.intent}</span
        >${r}
      </div>
      ${t?A`<div class="tb">${e.webQuery?this.webSearchBody(e,n):e.webFetch?this.webFetchBody(e):this.toolBody(e)}</div>`:j}
    </div>`}toolBody(e){return e.out===null?this.codeBlock(e.cmd,`${e.id}:cmd`):A`${e.cmd?this.codeBlock(e.cmd,`${e.id}:cmd`):j}${this.codeBlock(e.out,`${e.id}:out`)}`}webSearchBody(e,t){return A`<div class="wq"><span class="wl">${w(`query`)}</span><b>${e.webQuery}</b></div>
      ${t.length?A`<ol class="links">
            ${t.map(e=>A`<li><a href=${e.url} target="_blank" rel="noopener noreferrer">${e.title}</a><span class="host">${Ys(e.url)}</span></li>`)}
          </ol>`:j}
      ${e.out===null?j:t.length?A`<details class="rawfold"><summary>${w(`Full text`)}</summary>${this.codeBlock(e.out,`${e.id}:out`)}</details>`:this.codeBlock(e.out,`${e.id}:out`)}`}webFetchBody(e){let t=/^https?:\/\//.test(e.webFetch)?e.webFetch:``;return A`<div class="wq">
        <span class="wl">${w(`page`)}</span>${t?A`<a class="plink" href=${t} target="_blank" rel="noopener noreferrer">${t}</a>`:A`<b>${e.webFetch}</b>`}
      </div>
      ${e.out===null?j:this.codeBlock(e.out,`${e.id}:out`)}`}revealWebSearch(e,t=0){let n=0,r=this.model.rounds.length-1;for(let[i,a]of this.model.rounds.entries())for(let o of a.items)if(o.kind===`tool`&&o.webQuery===e&&n++===t)return this.openCards.set(o.id,!0),this.pinned=null,this.revealed=o.id,this.revealPending=!0,this.requestUpdate(),{round:i===r?null:i+1}}codeBlock(e,t){let n=A`<pre><code>${e.slice(0,Ks)}</code></pre>`;if(e.length<=Gs)return n;let r=this.folds.has(t);return A`<div>
      <div class="fold ${r?`open`:``}">${n}</div>
      <button type="button" class="foldbtn" @click=${()=>{r?this.folds.delete(t):this.folds.add(t),this.requestUpdate()}}>${w(r?`Show less`:S`Show all (${e.length} characters)`)}</button>
    </div>`}typing(){return A`<div class="typing"><span class="av av-a">A</span><span class="dots"><i></i><i></i><i></i></span><span class="meta">${w(`running`)}</span></div>`}};U([V({attribute:!1})],Q.prototype,`events`,void 0),U([V()],Q.prototype,`run`,void 0),U([V({attribute:!1})],Q.prototype,`stream`,void 0),U([V({attribute:`base-url`})],Q.prototype,`baseUrl`,void 0),U([V({attribute:!1})],Q.prototype,`client`,void 0),U([V({type:Boolean})],Q.prototype,`live`,void 0),U([V({attribute:!1})],Q.prototype,`round`,void 0),U([V({attribute:!1})],Q.prototype,`rows`,void 0),U([V({reflect:!0})],Q.prototype,`mode`,void 0),U([H()],Q.prototype,`version`,void 0),U([H()],Q.prototype,`behind`,void 0),U([H()],Q.prototype,`bulk`,void 0),U([H()],Q.prototype,`unseen`,void 0),U([H()],Q.prototype,`pinned`,void 0),U([H()],Q.prototype,`revealed`,void 0),U([kn(`.scroller`)],Q.prototype,`scroller`,void 0),Q=U([B(`ca-transcript`),D()],Q);var Xs=()=>({transcript:w(`Transcript`),input:w(`Input`),output:w(`Output`),definition:w(`Definition`)}),Zs=e=>oi((e.rounds||1)-1),Qs=new Set([`key`,`rows`,`launches`,`stream`,`task_detail_error`,`definition`,`io`]),$s=e=>({key:e,rows:[],launches:[],definition:null,io:{params:{},inputs:[],outputs:[],executor:`agent`,upstream:[],downstream:[]},stream:null}),ec=(e,t=e)=>A`<span class="pill p-${e}">${t}</span>`,tc=new Set([`completed`,`invalid_input`,`invalid_output`,`timeout`,`max_turns`,`stalled`,`skipped`,`running`]),nc=e=>tc.has(e)?e:`error`,rc=e=>typeof e==`string`?e:JSON.stringify(e)??String(e),ic=(e,t)=>{try{return JSON.stringify(e)===JSON.stringify(t)}catch{return!1}},ac=e=>!e.file.exists||e.status!=null&&e.status!==`valid`,oc=e=>A`<span aria-hidden="true">${e?`✓`:`✕`}</span><span class="sr">${w(e?`passed`:`failed`)}</span>`,$=class extends M{constructor(...e){super(...e),this.baseUrl=``,this.run=``,this.taskKey=null,this.view=`transcript`,this.round=null,this.live=!1,this.journal=[],this.plan=null,this.detail=null,this.launches=[],this.shownRound=-1,this.rounds=[],this.token=0,this.outcomes=new Map,this.producerOf=e=>{let t=this.writerOf(e);if(!t)return;let n=t.outputs.find(t=>t.path===e);return{name:I(t),written:!!n?.file.exists,outcome:this.outcomes.get(t.key)?.outcome}}}static{this.styles=[z,ho,Us,k`
      :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
      .taskmeta { flex: none; background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
        border-radius: 14px; padding: 10px 12px; margin-bottom: 8px; color: var(--fg2); }
      .tm-head { display: flex; gap: 12px; align-items: center; }
      .tm-av { width: 36px; height: 36px; border-radius: 11px; display: grid; place-items: center; font-size: 16px; flex: none;
        background: linear-gradient(135deg, #7c3aed, #22d3ee); color: #fff; box-shadow: 0 6px 18px rgba(124, 58, 237, 0.35); }
      .tm-av.py { background: var(--raise); color: var(--muted); box-shadow: none; }
      .tm-name { font-size: 15px; font-weight: 600; color: var(--fg); display: flex; gap: 8px; align-items: center; }
      .verdict { font-size: 12.5px; color: var(--fg); margin-top: 2px; }
      .verdict.bad { color: var(--err); }
      .verdict.warn { color: var(--warn); }
      .verdict.mut { color: var(--mut); }
      .whos { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
      .runchips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
      .who.ident { color: var(--fg2); font-family: var(--mono); font-weight: 500; }
      .spend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 6px; font-size: 12px; color: var(--mut); font-variant-numeric: tabular-nums; }
      .spend b { color: var(--fg); font-weight: 600; }
      .spend.quota { flex-direction: column; gap: 0; }
      .usage-wrap { overflow-x: auto; margin: 4px 0 12px; }
      /* sized to its content (a full-width table spreads a few numbers far apart); the wrap scrolls when it is wider */
      .usage { width: auto; border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }
      .usage th { text-align: right; font-weight: 600; color: var(--mut); font-size: 10.5px; white-space: nowrap;
        padding: 6px 14px; border-bottom: 1px solid var(--line2); vertical-align: bottom; }
      .usage td { text-align: right; padding: 8px 14px; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: baseline; }
      .usage th:first-child, .usage td:first-child { padding-left: 4px; }
      .usage td.l.jmono { font-size: 12px; }
      /* the subscription readings wrap at a narrow width rather than push the table past the edge */
      .usage td.l:not(:first-child):not(.jmono) { white-space: normal; min-width: 12ch; }
      .usage th.l, .usage td.l { text-align: left; }
      .usage tr.hop td { padding-top: 4px; padding-bottom: 4px; color: var(--mut); }
      .usage tr.hop td:first-child { padding-left: 28px; }
      .runchip { font-size: 11px; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--line2); color: var(--fg2); }
      .runchip.ok { border-color: rgba(52, 211, 153, 0.35); }
      .runchip.bad { border-color: rgba(248, 113, 113, 0.4); color: var(--err); }
      .io-fold { margin-top: 6px; }
      .io-fold > summary, .launch > summary { cursor: pointer; color: var(--mut); }
      .searches { margin: 4px 0 0; padding-left: 22px; }
      .unread { color: var(--warn); margin-top: 4px; }
      .qlink { background: none; border: 0; padding: 0; color: var(--info); cursor: pointer; text-align: left; font: inherit; }
      .qlink:hover { text-decoration: underline; }

      .tviews { flex: none; display: flex; gap: 4px; margin: 2px 0 8px; border-bottom: 1px solid var(--line); }
      .tview { background: none; border: 0; border-bottom: 2px solid transparent; color: var(--mut); padding: 6px 14px; cursor: pointer; }
      .tview:hover { color: var(--fg2); }
      .tview.sel { color: var(--fg); border-bottom-color: var(--live); }
      .tview .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--fg2); }

      .pane { flex: 1 1 auto; min-height: 0; overflow: auto; }
      .upstream { margin-bottom: 12px; }
      .up-hd { display: flex; align-items: center; gap: 10px; margin: 2px 0 6px; }
      .down { display: flex; flex-wrap: wrap; gap: 8px; }
      .notrans { flex: 1 1 auto; border: 1px solid var(--line); border-radius: 14px; }
      details.upstream > summary { cursor: pointer; list-style: none; }
      details.upstream > summary::-webkit-details-marker { display: none; }
      .params td { vertical-align: top; }
      .from { color: var(--live); white-space: nowrap; }
    `]}willUpdate(e){(e.has(`run`)||e.has(`taskKey`)||e.has(`client`))&&this.fetch(),this.outcomes=this.plan?jr(this.journal,this.plan):new Map}async fetch(){let e=++this.token;this.detail=null,this.launches=[],this.shownRound=-1,this.rounds=[];let{run:t,taskKey:n}=this;if(!t||!n||!this.client)return;let r;try{r=await this.client.task(t,n)}catch{r=$s(n)}e===this.token&&(this.detail=r)}openTask(e,t){e.preventDefault(),n(this,`ca-open-task`,{key:t})}isPy(e){return W(e.io)||e.rows.some(W)}hadSession(e){return!this.isPy(e)&&(!!e.stream||e.launches.length>0||e.rows.some(G))}shownView(e){return this.view===`transcript`&&this.isPy(e)&&!e.stream?`output`:this.view}stateOf(e,t){return t?`running`:Qr(e.rows,this.outcomes.get(e.key))}writerOf(e){return this.detail?.io.upstream.find(t=>t.outputs.some(t=>t.path===e))}notStartedCause(e){let t=pi(this.outcomes.get(e.key)??{attempts:e.rows,cause:null},this.outcomes,this.run,e=>this.writerOf(e)?.key);if(t)return t;let n=di(e.rows[e.rows.length-1]?.reason)[0],r=n?this.writerOf(n.path):void 0;return n?fi(J(n.path,this.run),n.problem,r?{name:I(r)}:void 0):``}culprit(e){let t=di(e.rows[e.rows.length-1]?.reason)[0],n=t?.producer?this.outcomes.get(t.producer):void 0;if(n)return n;let r=t?this.writerOf(t.path):void 0;if(r)return r;let i=this.outcomes.get(e.key)?.cause;return i?this.outcomes.get(i):void 0}link(e){return A`<a class="lnk" href="#" @click=${t=>this.openTask(t,e.key)}>${I(e)}</a>`}render(){let e=this.taskKey;if(!e)return A`<div class="blank"><span class="ic" aria-hidden="true">✦</span><b>${w(`No task selected`)}</b></div>`;let t=this.detail;if(!t)return A`<div class="taskmeta meta"><strong>${e}</strong> ${w(`Loading…`)}</div>`;let n=t.launches.length>0&&this.live,r=this.shownView(t);return A`${this.renderMeta(e,t,n)} ${this.renderViews(t,r)}
      ${t.stream?A`<ca-transcript .run=${this.run} .stream=${t.stream} base-url=${this.baseUrl} .client=${this.client} .live=${n}
            .rows=${t.rows} .round=${this.round} mode=${r===`transcript`?`full`:r===`input`?`tabs`:`none`}
            @rounds-changed=${e=>{this.launches=e.detail.launches,this.shownRound=e.detail.shown,this.rounds=e.detail.rounds}}></ca-transcript>`:r===`transcript`?this.noTranscript(t,n):j}
      ${r===`transcript`?j:A`<div class="pane">${this.renderPane(t,r,n)}</div>`}`}noTranscript(e,t){let n=this.stateOf(e,t);if(n===`not_started`){let t=this.culprit(e);return A`<div class="blank notrans"><span class="ic" aria-hidden="true">⊘</span><b>${F(w(`No transcript`),Yr(n))}</b>
        ${t?A`<span>${w(`Earlier task`)} ${Aa(this,I(t),t)}</span>`:j}</div>`}return this.hadSession(e)?A`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${w(`No transcript`)}</b>
        <span>${w(`Transcript not saved (keep_transcripts = false)`)}</span></div>`:A`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${F(w(`No transcript`),Yr(n))}</b></div>`}verdict(e,t){let n=e.rows,r=n.filter(G),i=n[n.length-1],a=this.stateOf(e,t);switch(a){case`running`:return[w(`Running`),``];case`waiting`:return[w(`Waiting`),`mut`];case`skipped`:return[w(`Skipped`),`mut`];case`not_started`:{let t=this.notStartedCause(e);return[w(t?S`Not started: ${t}`:`Not started`),`warn`]}case`failed`:{let e=J(i?.reason,this.run)||q(i?.stop);return[r.length>1?w(S`Failed on all ${r.length} attempts: ${e}`):w(S`Failed: ${e}`),`bad`]}}if(!i)return[Yr(a),``];let o=r.filter(e=>!e.ok);if(o.length){let e=J(o[0]?.reason,this.run)||q(o[0]?.stop);return[o.length===1?w(S`Done on attempt ${r.length} after 1 failed attempt. First failure: ${e}`):w(S`Done on attempt ${r.length} after ${o.length} failed attempts. First failure: ${e}`),``]}let s=(i.rounds||1)-1+(i.hook_errors??[]).length;if(s>0){let e=[...(i.hook_errors??[]).flat(),...(i.round_errors??[]).flat(),...this.rounds.flatMap(e=>e.rejectedWith)],t=e[0]?Is(J(e[0],this.run)):``;return t?[w(s===1?S`Done after 1 correction. First failed check: ${t}`:S`Done after ${s} corrections. First failed check: ${t}`),``]:[w(s===1?`Done after 1 correction`:S`Done after ${s} corrections`),``]}let c=ui(i.hops);return c?[w(S`Done after a model switch: ${c}`),``]:[w(`Done`),``]}streamModel(){for(let e=this.launches.length-1;e>=0;e--){let t=this.launches[e],n=t?Cs(t).model:``;if(n)return n}return``}renderMeta(e,t,n){let{rows:r,launches:i}=t,a=this.isPy(t),o=this.hadSession(t),s=r.slice().sort((e,t)=>String(e.ts).localeCompare(String(t.ts))),c=s[s.length-1],l=i[0],u={agent:xs(l?.cmd?l.cmd.split(` `)[0]:c?.agent),model:l?.model||c?.model||this.streamModel(),role:l?.role||``},d=o?[...new Set(s.map(e=>e.model).filter(e=>!!e&&e!==u.model))]:[],f=r[0],p=r.filter(G),m=Object.entries(t).filter(([e])=>!Qs.has(e)),[h,g]=this.verdict(t,n),_=w(a?`Python task`:`Agent task`),v=this.plan?.nodes.find(e=>e.key===t.key);return A`<div class="taskmeta">
      <div class="tm-head">
        <span class="tm-av ${a?`py`:``}" title=${_}><span aria-hidden="true">${a?`⚙`:`✦`}</span><span class="sr">${_}</span></span>
        <div style="min-width:0">
          <div class="tm-name" title=${e}>${f?I(f):v?I(v):e.replace(/^python:/,``)} ${n?ec(`running`,w(`running`)):j}</div>
          <div class="verdict ${g}">${h}</div>
          ${o?A`<div class="whos">
                ${Hs(u)}${this.identityChip(p)}
                ${d.length?A`<span class="meta">${d.length===1?w(S`Earlier attempts used model ${d[0]??``}`):w(S`Earlier attempts used models ${d.join(`, `)}`)}</span>`:j}
              </div>`:j}
          ${i.length?A`<div class="meta">${i.length===1?w(`1 agent session running`):w(S`${i.length} agent sessions running`)}</div>`:j}
          ${this.spendLine(Br(r))}
          ${this.quotaLine(p)}
        </div>
      </div>
      ${p.length?A`<div class="runchips">${p.map(e=>this.runChip(e,o))}</div>`:j}
      ${this.searchFold(p)}
      ${sn(p)?A`<div class="meta unread" title=${w(`Event types from the coding agent that this contraagent version does not recognize`)}>
            <span aria-hidden="true">⚠</span> ${w(S`Unrecognized events: ${sn(p)}`)}
          </div>`:j}
      ${t.task_detail_error?A`<div class="meta v-bad">${w(S`The task_detail callback failed: ${t.task_detail_error??``}`)}</div>`:j}
      ${i.map(e=>A`<details class="launch">
          <summary>${F(w(S`Process ${e.pid??`—`}`),e.key||``)}</summary>
          <div class="meta">${F(w(S`Plugin ${e.plugin||w(`none`)}`),w(S`Model ${e.model||`—`}`),w(S`Role ${e.role||w(`none`)}`))}</div>
        </details>`)}
      ${m.map(([e,t])=>A`<details class="io-fold"><summary>${e}</summary><ca-json-tree .value=${t}></ca-json-tree></details>`)}
    </div>`}identityChip(e){let t=[...new Set(e.flatMap(e=>[...(e.hops??[]).map(e=>e.credential),e.credential]).filter(e=>!!e))];return t.length?A`<span class="who ident" title=${[w(`What the coding agent authenticated as: an account or an API key (credential)`),...t.map(ci)].filter(Boolean).join(`
`)}
          ><span class="who-l">${w(`identity`)}</span>${t.map(si).join(`, `)}</span
        >`:j}searchFold(e){let t=e.flatMap(e=>e.web_queries??[]),n=new Map;return t.length?A`<details class="io-fold">
          <summary>${t.length===1?w(`1 web search`):w(S`${t.length} web searches`)}</summary>
          <ol class="meta searches">
            ${t.map(e=>{let t=n.get(e)??0;return n.set(e,t+1),A`<li><button class="qlink jmono" @click=${()=>this.revealSearch(e,t)}>
                ${e}
              </button></li>`})}
          </ol>
        </details>`:j}revealSearch(e,t){let r=this.transcriptEl?.revealWebSearch(e,t);n(this,`ca-navigate`,r?{view:`transcript`,round:r.round}:{view:`transcript`})}spendLine(e){return e?A`<div class="spend">
      <b title=${w(`Reported by the coding agent`)}>${on(e.cost)}</b>
      <span>${w(S`Tokens: ${R(e.input)} input, ${R(e.output)} output, ${R(e.cache_read)} cache read, ${R(e.cache_creation)} cache write`)}</span>
      <span>${e.calls===1?w(`1 API call`):w(S`${e.calls} API calls`)}</span>
    </div>`:j}quotaLine(e){let t=Kr(this.journal.length?this.journal:e),n=e[0],r=e[e.length-1],i=n?Jr(n,t).start:null;if(!i||!r)return j;let a=Jr(r,t).next;return A`<div class="spend quota">
      <span title=${Ea(i)}>${w(S`Usage at session start: ${Ta(i)}`)}</span>
      ${a?A`<span title=${Ea(a)}>${w(S`Usage after this task: ${Ta(a)}`)}</span>`:j}
    </div>`}runChip(e,t){let n=e.ok,r=J(e.reason,this.run),i=ui(e.hops),a=[w(S`Ended ${P(e.ts,!0)}`),Zs(e),t&&e.model?w(S`Model ${e.model}`):``,i?w(S`Model switch: ${i}`):``,r,e.route||``].filter(Boolean).join(`
`),o=e.cost_usd!==null&&e.cost_usd!==void 0?on(e.cost_usd):``;return A`<span class="runchip ${n?`ok`:`bad`}" title=${a}>
      ${oc(n)} ${F(ei(e.attempt),q(e.stop,e.reason),N(e.wall_s),o)}
    </span>`}renderViews(e,t){let r=e.io,a=this.isPy(e)&&!e.stream,o={input:new Set([...r.inputs.map(e=>e.path),...r.upstream.flatMap(e=>e.outputs.map(e=>e.path))]).size+Object.keys(r.params).length,output:r.outputs.length};return A`<div class="tviews" role="tablist">
      ${i.filter(e=>!(a&&e===`transcript`)).map(e=>{let r=Xs()[e];return A`<button type="button" role="tab" aria-selected=${e===t} class="tview ${e===t?`sel`:``}"
          @click=${()=>n(this,`ca-navigate`,{view:e})}>
          ${r}${o[e]?A`<span class="badge">${o[e]}</span>`:j}
        </button>`})}
    </div>`}renderPane(e,t,n){return t===`input`?this.inputPane(e,n):t===`output`?this.outputPane(e):A`<ca-definition .definition=${e.definition??null} memory="task-definition"></ca-definition>`}inputPane(e,t){let n=e.io,r=Object.entries(n.params),i=new Set(n.inputs.map(e=>e.path)),a=e=>n.upstream.some(t=>t.outputs.some(t=>t.path===e.path)),o=n.inputs.filter(e=>!a(e)),s=[...n.upstream].sort((e,t)=>Number(t.outputs.some(ac))-Number(e.outputs.some(ac))),c=e=>n.upstream.find(t=>t.outputs.some(t=>t.file.exists&&ic(t.file.content,e)));return A`<h4 class="sect-h">${w(`Parameters`)}</h4>
      ${r.length?A`<table class="ct-fields params">
            ${r.map(([e,t])=>{let n=c(t);return A`<tr>
                <td class="jmono">${e}</td>
                <td>${typeof t==`object`&&t?A`<ca-json-tree .value=${t} .open=${0}></ca-json-tree>`:A`<span class="jmono">${rc(t)}</span>`}</td>
                <td>${n?A`<span class="from">${w(A`From ${this.link(n)}`)}</span>`:j}</td>
              </tr>`})}
          </table>`:A`<div class="meta">${w(`No parameters`)}</div>`}
      <h4 class="sect-h">${w(`Inputs from earlier tasks`)}</h4>
      ${s.length?s.map(e=>this.upstreamGroup(e,i)):A`<div class="meta">${w(`No earlier tasks`)}</div>`}
      ${o.length?A`<h4 class="sect-h">${w(`Other input files`)} <span class="meta">${w(`Checked when the task starts`)}</span></h4>
            ${o.map(e=>mo(e,`input`,this.run))}`:!n.inputs.length&&!s.length?A`<h4 class="sect-h">${w(`Input files`)}</h4>
              <div class="meta">${w(`No input files`)}</div>`:j}
      ${this.isPy(e)?j:this.promptSection(e,t)}`}upstreamGroup(e,t){let n=e.outputs.some(ac),r=e.outputs.filter(e=>!e.file.exists).length,i=e.outputs.filter(e=>e.file.exists&&e.status!=null&&e.status!==`valid`).length,a=e.outputs.length-r-i,o=W(e)?w(`Python task`):w(`Agent task`),s=this.outcomes.get(e.key)?.outcome,c=e.outputs.length?F(r?w(r===1?`1 output file is missing`:S`${r} output files are missing`):``,i?w(i===1?`1 output file failed checks`:S`${i} output files failed checks`):``,n?``:w(a===1?`1 output file passed`:S`${a} output files passed`)):w(`No output files`),l=A`<div class="up-hd">
      <span class="k-ic ${W(e)?``:`llm`}" title=${o}><span aria-hidden="true">${W(e)?`⚙`:`✦`}</span><span class="sr">${o}</span></span>
      ${this.link(e)}
      ${s&&s!==`done`?A`<span class="pill o-${s}">${Yr(s)}</span>`:j}
      <span class="meta">${c}</span>
      ${e.outputs.some(e=>t.has(e.path))?A`<span class="ct-chip" title=${w(`Also declared as an input of this task`)}>${w(`Also an input`)}</span>`:j}
    </div>`,u=e.outputs.map(e=>mo(e,`output`,this.run,{producerOf:this.producerOf}));return n||!e.outputs.length?A`<div class="upstream">${l}${u}</div>`:A`<details class="upstream"><summary>${l}</summary>${u}</details>`}promptSection(e,t){let n=this.launches.length,r=this.shownRound,i=this.rounds[r],a=this.rounds[this.rounds.length-1]?.tryNo??1,o=this.launches[r]?.prompt??``,s=this.stateOf(e,t);return A`<h4 class="sect-h">${w(`Prompt`)}${n>1&&i?A` <span class="meta">${gs(i,a)}: ${_s(i)}</span>`:j}</h4>
      ${o?A`<ca-markdown .text=${o}></ca-markdown>`:A`<div class="meta">${e.stream?w(`Loading…`):this.hadSession(e)?w(`Prompt not saved (keep_transcripts = false)`):F(w(`No prompt`),Yr(s))}</div>`}`}usageTable(e){let t=e.filter(e=>G(e)&&(e.usage||e.cost_usd!==null&&e.cost_usd!==void 0));if(!t.length)return j;let n=A`<td class="jdim">—</td>`,r=Kr(this.journal.length?this.journal:e),i=t.some(e=>(e.quota??[]).length),a=A`<td class="l jdim">—</td>`,o=(e,t)=>e?A`<td class="l" title=${Ea(e)}>${(e.credential??``)===(t??``)?Ta(e):Da(e)}</td>`:a;return A`<h4 class="sect-h">${w(`Tokens and cost`)}</h4>
      <div class="usage-wrap"><table class="usage">
        <tr>
          <th class="l"></th><th>${w(`Input`)}</th><th>${w(`Output`)}</th><th>${w(`Cache read`)}</th><th>${w(`Cache write`)}</th>
          <th>${w(`API calls`)}</th><th title=${w(`Reported by the coding agent`)}>${w(`Cost`)}</th><th class="l">${w(`Identity`)}</th>
          ${i?A`<th class="l" title=${w(`Subscription usage when the agent session started (account-wide)`)}>${w(`Usage at start`)}</th>
                <th class="l" title=${w(`The first reading of the same account after this attempt ended`)}>${w(`Usage after`)}</th>`:j}
        </tr>
        ${t.map(e=>{let t=e.usage,a=e.hops??[];return A`<tr>
              <td class="l">${ei(e.attempt)}</td>
              ${t?A`<td>${R(t.input)}</td><td>${R(t.output)}</td><td>${R(t.cache_read)}</td><td>${R(t.cache_creation)}</td><td>${t.calls}</td>`:A`${n}${n}${n}${n}${n}`}
              <td>${on(e.cost_usd)}</td><td class="l" title=${ci(e.credential)||j}>${si(e.credential)||`—`}</td>
              ${i?A`${o(Jr(e,r).start,e.credential)}${o(Jr(e,r).next,e.credential)}`:j}
            </tr>
            ${a.length>1?a.map(e=>A`<tr class="hop">
                    <td class="l">${F(e.model||e.route||`—`,q(e.stop))}</td>
                    <td></td><td></td><td></td><td></td><td></td>
                    <td>${on(e.cost_usd)}</td><td class="l" title=${ci(e.credential)||j}>${si(e.credential)||`—`}</td>
                    ${i?A`<td></td><td></td>`:j}
                  </tr>`):j}`})}
      </table></div>`}outputPane(e){let t=e.io,n=e.rows[e.rows.length-1];return A`<h4 class="sect-h">${w(`Output files`)}</h4>
      ${t.outputs.length?t.outputs.map(e=>mo(e,`output`,this.run,{producerOf:this.producerOf})):A`<div class="meta">${w(`No output files`)}</div>`}
      ${n?A`<h4 class="sect-h">${w(`Outcome`)}</h4>
            <div class="ct-in">
              ${ec(nc(n.stop),q(n.stop,n.reason))}
              ${G(n)?A`<span class="meta">${F(ei(n.attempt),N(n.wall_s),Zs(n))}</span>`:j}

            </div>`:j}
      ${this.usageTable(e.rows)}
      <h4 class="sect-h">${w(`Later tasks`)}</h4>
      ${t.downstream.length?A`<div class="down">${t.downstream.map(e=>Aa(this,I(e),e))}</div>`:A`<div class="meta">${w(`No later tasks`)}</div>`}`}};U([V({attribute:!1})],$.prototype,`client`,void 0),U([V({attribute:`base-url`})],$.prototype,`baseUrl`,void 0),U([V()],$.prototype,`run`,void 0),U([V({attribute:!1})],$.prototype,`taskKey`,void 0),U([V()],$.prototype,`view`,void 0),U([V({attribute:!1})],$.prototype,`round`,void 0),U([V({type:Boolean})],$.prototype,`live`,void 0),U([V({attribute:!1})],$.prototype,`journal`,void 0),U([V({attribute:!1})],$.prototype,`plan`,void 0),U([H()],$.prototype,`detail`,void 0),U([kn(`ca-transcript`)],$.prototype,`transcriptEl`,void 0),U([H()],$.prototype,`launches`,void 0),U([H()],$.prototype,`shownRound`,void 0),U([H()],$.prototype,`rounds`,void 0),$=U([B(`ca-task-view`),D()],$);var sc=()=>[{id:`overview`,label:w(`Overview`),icon:`◎`},{id:`tasks`,label:w(`Tasks`),icon:`≡`},{id:`journal`,label:w(`History`),icon:`▤`,tip:`journal.jsonl`},{id:`outputs`,label:w(`Outputs`),icon:`▣`},{id:`definitions`,label:w(`Definitions`),icon:`⌘`},{id:`procs`,label:w(`Processes`),icon:`⚙`},{id:`stream`,label:w(`Task detail`),icon:`✦`}],cc=250,lc=class extends M{constructor(){super(),new Fn(this)}createRenderRoot(){return this}render(){return new Date().toLocaleTimeString(Jt(),{hour12:!1})}};lc=U([B(`ca-clock`),D()],lc);var uc=class extends M{constructor(...e){super(...e),this.baseUrl=``,this.history=`url`,this.run=``,this.locale=``,this.live=!1,this.pickerOpen=!1,this.qDraft=null,this.mainScroll=new gi(`main`),this.pendingScroll=null,this.qTimer=null,this.cleanups=[]}static{this.styles=[z,k`
      :host { display: flex; flex-direction: column; height: 100%; min-height: 0; font: 13px/1.5 var(--sans); color: var(--fg); }
      header { flex: none; display: flex; gap: 14px; align-items: center; padding: 10px 18px; border-bottom: 1px solid var(--line);
        background: rgba(6, 10, 17, 0.75); backdrop-filter: blur(10px); position: relative; z-index: 20; }
      .brand { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; letter-spacing: 0.02em; }
      .brand svg { width: 22px; height: 22px; }
      .logo-core { fill: var(--live); transform-origin: 12px 12px; }
      .logo-ring { stroke: var(--live); opacity: 0.5; transform-origin: 12px 12px; }
      :host([live]) .logo-core { animation: core-beat 1.8s var(--ease) infinite; }
      :host([live]) .logo-ring { animation: turn 7s linear infinite; }
      .runbtn { display: flex; align-items: center; gap: 10px; min-width: 0; max-width: 52vw; cursor: pointer; padding: 6px 13px;
        border-radius: 999px; background: var(--panel); border: 1px solid var(--line); color: var(--fg); transition: border-color 0.2s, background 0.2s; }
      .runbtn:hover { border-color: var(--line2); background: var(--panel2); }
      .rn { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: none; max-width: 40%; }
      .rs { color: var(--mut); font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .chev { color: var(--mut); }
      .hdr-right { margin-left: auto; display: flex; align-items: center; gap: 12px; min-width: 0; }
      .nowline { font-size: 12px; color: var(--fg2); white-space: nowrap; overflow: hidden; max-width: 40vw;
        display: inline-flex; align-items: center; gap: 4px; }
      .clock { font-family: var(--mono); font-size: 11.5px; color: var(--mut); }
      .langs { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; overflow: hidden; }
      .langs button { background: none; border: 0; padding: 2px 9px; font-size: 11px; color: var(--mut); cursor: pointer; }
      .langs button:hover { color: var(--fg2); }
      .langs button[aria-pressed='true'] { background: var(--raise); color: var(--fg); }
      .live-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--ok); display: inline-block; animation: breathe 1.8s ease-in-out infinite; }
      .live-dot.off { background: #3b4760; animation: none; box-shadow: none; }

      nav { flex: none; display: flex; gap: 2px; padding: 6px 18px 0; position: relative; overflow-x: auto; scrollbar-width: none; align-items: center; }
      nav::-webkit-scrollbar { display: none; }
      .tab { position: relative; background: none; border: none; padding: 8px 14px 11px; color: var(--mut); cursor: pointer;
        font-weight: 500; white-space: nowrap; transition: color 0.2s; }
      .tab:hover { color: var(--fg2); }
      .tab.sel { color: var(--fg); }
      .tab-ic { opacity: 0.55; margin-right: 6px; font-size: 12px; }
      .tab.sel .tab-ic { opacity: 1; color: var(--live); }
      .tab.panel-tab { color: var(--llm); }
      .tab.panel-tab:hover { color: var(--fg); }
      .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--fg2); font-variant-numeric: tabular-nums; }
      .badge.err { background: var(--err-a); color: var(--err); }
      .badge.live { background: var(--live-a); color: var(--live); }
      .tab-sep { width: 1px; height: 18px; background: var(--line2); margin: 0 8px 3px; flex: none; align-self: center; }
      .tab-ind { position: absolute; bottom: 0; left: 0; width: 0; height: 2px; border-radius: 2px;
        background: linear-gradient(90deg, var(--live), var(--llm)); transition: left 0.3s var(--ease), width 0.3s var(--ease); }
      .tab-ind.init { transition: none; }
      .tabhint { margin-left: auto; padding-left: 12px; white-space: nowrap; }

      .bar { flex: none; display: flex; gap: 8px; padding: 8px 18px; border-top: 1px solid var(--line); align-items: center; flex-wrap: wrap; }
      .bar select, .bar input { background: var(--panel); color: var(--fg); border: 1px solid var(--line); border-radius: 8px;
        padding: 5px 9px; outline: none; font: inherit; font-size: 12px; }
      .bar input:focus, .bar select:focus { border-color: var(--live); }

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
    `]}connectedCallback(){super.connectedCallback(),Yt(Zt(this.locale)?this.locale:Qt()),this.store=new Or({baseUrl:this.baseUrl}),this.snap=this.store.snapshot,this.cleanups.push(this.store.subscribe(e=>{this.snap=e,this.pickDefaultRun()}),this.store.onNewRow(e=>this.announce(e))),this.router=new re(this.history,(e,t)=>this.onRoute(e,t),this.run?{run:this.run}:{}),this.router.start(),this.store.start();let e=e=>this.onKey(e),t=e=>{this.pickerOpen&&!e.composedPath().some(e=>e instanceof HTMLElement&&(e.localName===`ca-run-picker`||e.classList.contains(`runbtn`)))&&(this.pickerOpen=!1)},n=()=>this.moveTabIndicator();document.addEventListener(`keydown`,e),document.addEventListener(`click`,t),addEventListener(`resize`,n),this.cleanups.push(()=>document.removeEventListener(`keydown`,e),()=>document.removeEventListener(`click`,t),()=>removeEventListener(`resize`,n)),this.addEventListener(`ca-open-task`,e=>{this.navigate({tab:`stream`,key:e.detail.key,...e.detail.view?{view:e.detail.view}:{}})}),this.addEventListener(`ca-navigate`,e=>this.navigate(e.detail)),this.addEventListener(`ca-select-run`,e=>this.navigate({run:e.detail.run})),this.addEventListener(`ca-filter`,e=>this.navigate(e.detail))}disconnectedCallback(){super.disconnectedCallback();for(let e of this.cleanups.splice(0))e();this.router.stop(),this.store.stop(),this.mainScroll.detach()}navigate(e,t={}){this.router.navigate(e,t)}onRoute(e,t){this.route=e,t!==`replace`&&(this.qDraft=null),this.store.selectRun(e.run),this.pickDefaultRun(),t!==`replace`&&(this.pendingScroll=t)}pickDefaultRun(){let e=this.snap.runs[0];!this.route.run&&e&&this.navigate({run:e.run},{replace:!0})}announce(e){let t=I(e),n=J(e.reason,this.snap.run).slice(0,110);e.stop===`invalid_input`?this.toasts?.show(`warn`,w(S`${t}: not started`),n):xr(e)?this.toasts?.show(`err`,w(S`${t}: ${q(e.stop)}`),n):(e.hops||[]).length>1?this.toasts?.show(`llm`,w(S`${t}: model switch`),ui(e.hops,e.wall_s).slice(0,110)):this.toasts?.show(`ok`,w(S`${t}: done`),F(N(e.wall_s),e.model))}tabs(){return[...sc().map(e=>({...e,panel:!1})),...this.snap.info.panels.map(e=>({id:`panel:${e.name}`,label:e.title||e.name,icon:e.icon||`▤`,tip:e.description?w(S`${e.description} (custom view)`):w(`Custom view`),panel:!0}))]}onKey(e){let t=e.composedPath()[0];if(!(t instanceof HTMLElement&&t.matches(`input, select, textarea`)||e.metaKey||e.ctrlKey||e.altKey)){if(e.key===`r`)e.preventDefault(),this.pickerOpen=!0;else if(e.key===`/`)e.preventDefault(),this.renderRoot.querySelector(`.bar input`)?.focus();else if(/^[1-9]$/.test(e.key)){let t=this.tabs()[Number(e.key)-1];t&&this.navigate({tab:t.id})}}}willUpdate(e){e.has(`snap`)&&(this.live=wr(this.snap.state,Cr(this.snap.runs,this.snap.run)),document.title=w(S`${this.snap.info.title} monitor`))}updated(e){e.has(`locale`)&&Zt(this.locale)&&this.locale!==Jt()&&Yt(this.locale),this.history===`url`&&(document.documentElement.lang=Jt()),this.lang=Jt(),this.moveTabIndicator(),this.main&&this.mainScroll.attach(this.main),this.pendingScroll&&=(this.pendingScroll===`push`?this.mainScroll.reset():this.mainScroll.restore(),null)}moveTabIndicator(){let e=this.renderRoot.querySelector(`.tab.sel`),t=this.renderRoot.querySelector(`.tab-ind`);e&&t&&(t.style.left=`${e.offsetLeft+10}px`,t.style.width=`${Math.max(12,e.offsetWidth-20)}px`,t.classList.contains(`init`)&&requestAnimationFrame(()=>t.classList.remove(`init`)))}setQ(e){this.qDraft=e,this.qTimer&&clearTimeout(this.qTimer),this.qTimer=setTimeout(()=>{this.qTimer=null,this.navigate({q:e})},cc)}runLine(e){let t=bi(e),n=this.snap.state.ready?Br(this.snap.state.journal)?.cost:e.cost_usd,r=n==null?``:on(n),i=Oa(this.accounts(e)),a=F(t==null?``:w(S`took ${N(t)}`),r,i,e.running?w(`running`):``);if(!this.snap.state.ready)return a;let o=Nr(jr(this.snap.state.journal,this.snap.state.plan));return F(w(S`${o.done+o.recovered} of ${o.total} tasks done`),a)}accounts(e){return this.snap.state.ready?qr(this.snap.state.journal):e.quota??[]}triesLine(){let{tries:e,notStarted:t}=vi(this.snap.state.journal);return F(w(e===1?`1 attempt`:S`${e} attempts`),t?K(`not_started`,t):``)}pickLocale(e){this.locale=e,$t(e)}render(){if(!this.snap||!this.route)return j;let{snap:e,route:t}=this,n=Cr(e.runs,e.run),r=Tr(e.state.procs),i=n?.tasks,a=n?.running?`live`:i?.total?i.failed||i.not_started?`warn`:`ok`:``;return A`
      <header>
        <div class="brand">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle class="logo-ring" cx="12" cy="12" r="9.5" fill="none" stroke-width="1.5" stroke-dasharray="4 3" />
            <circle class="logo-core" cx="12" cy="12" r="4" />
          </svg>
          <span>${e.info.title}</span>
        </div>
        <button type="button" class="runbtn" title=${w(`Switch run (r)`)} @click=${()=>this.pickerOpen=!this.pickerOpen}>
          <span class="dot ${a}" aria-hidden="true"></span>
          <span class="rn">${t.run||`—`}</span>
          <span class="rs" title=${n?ka(this.accounts(n)):``}>${n?this.runLine(n):``}</span>
          <span class="chev" aria-hidden="true">▾</span>
        </button>
        <div class="hdr-right">
          <span class="nowline">${r.length?A`${w(`Running`)} ${r.slice(0,3).map(e=>Aa(this,I(e),{key:e.key}))}${r.length>3?A` <span>+${r.length-3}</span>`:j}`:j}</span>
          <span class="langs" role="group" aria-label=${w(`Language`)}>
            ${Me.map(e=>A`<button type="button" lang=${e} aria-pressed=${e===Jt()} @click=${()=>this.pickLocale(e)}>
                ${Kt[e]}
              </button>`)}
          </span>
          <span title=${e.connected?w(`Connected to the monitor server`):w(`Not connected to the monitor server`)}
            ><span class="live-dot ${e.connected?``:`off`}"></span><span class="sr">${e.connected?w(`Connected to the monitor server`):w(`Not connected to the monitor server`)}</span></span
          >
          <ca-clock class="clock"></ca-clock>
        </div>
        <ca-run-picker style="left:110px" .runs=${e.runs} current=${t.run} ?open=${this.pickerOpen}
          @close=${()=>this.pickerOpen=!1}></ca-run-picker>
      </header>
      ${this.renderTabs(r.length)} ${this.renderBar()}
      <main class=${t.tab===`stream`?`stream`:``}>${this.renderView()}</main>
      <ca-toasts></ca-toasts>
    `}renderTabs(e){let{state:t}=this.snap,{tries:n}=vi(t.journal),r=Nr(jr(t.journal,t.plan)),i=t.journal.filter(e=>G(e)&&xr(e)).length,a=a=>a===`tasks`?[r.total||``,r.running?`live`:``]:a===`journal`?[n||``,i?`err`:``]:a===`procs`?[t.procs?.alive&&e||``,`live`]:null,o=this.tabs();return A`<nav>
      ${o.map((e,t)=>{let n=a(e.id);return A`${e.panel&&!o[t-1]?.panel?A`<span class="tab-sep" title=${w(`Custom views`)}></span>`:j}
          <button type="button" class="tab ${e.panel?`panel-tab`:``} ${e.id===this.route.tab?`sel`:``}" title=${e.tip??j}
            @click=${()=>this.navigate({tab:e.id})}>
            <span class="tab-ic" aria-hidden="true">${e.icon}</span>${e.label}${n&&n[0]!==``?A`<span class="badge ${n[1]}">${n[0]}</span>`:j}
          </button>`})}
      <span class="tab-ind init"></span>
      <span class="tabhint meta" role="note" aria-label=${w(`Keyboard shortcuts`)}
        ><span aria-hidden="true"><span class="kbd">1</span>–<span class="kbd">${Math.min(9,o.length)}</span> ${w(`Tabs`)} |
          <span class="kbd">r</span> ${w(`Runs`)} | <span class="kbd">/</span> ${w(`Filter`)}</span></span
      >
    </nav>`}renderBar(){let{route:e}=this;if(e.tab!==`tasks`&&e.tab!==`journal`)return j;let{state:t}=this.snap,n=jr(t.journal,t.plan),r=Nr(n).total,i=[...new Set([...n.values()].map(e=>e.kind))].sort();return A`<div class="bar">
      <select title=${w(`Kind`)} aria-label=${w(`Kind`)} @change=${e=>this.navigate({kind:e.target.value})}>
        <option value="" ?selected=${!e.kind}>${w(`All kinds`)}</option>
        ${i.map(t=>A`<option ?selected=${t===e.kind}>${t}</option>`)}
      </select>
      <input placeholder=${w(`Filter`)} aria-label=${w(`Text filter`)} size="22" title=${w(`Text filter (/)`)} .value=${this.qDraft??e.q}
        @input=${e=>this.setQ(e.target.value)} />
      <span class="meta">${e.tab===`journal`?this.triesLine():w(r===1?`1 task`:S`${r} tasks`)}</span>
    </div>`}renderView(){let{snap:e,route:t}=this,{state:n}=e;if(!t.run)return A`<div class="blank"><span class="ic" aria-hidden="true">✦</span><b>${w(`No runs yet`,{id:`no-runs-yet`})}</b></div>`;let r=Cr(e.runs,e.run),i=wr(n,r),a=this.qDraft??t.q;switch(t.tab){case`overview`:return A`<ca-overview .state=${n} .summary=${r} .info=${e.info} .run=${t.run} .layer=${t.layer} .unit=${t.unit}></ca-overview>`;case`tasks`:return A`<ca-task-table .run=${t.run} .journal=${n.journal} .plan=${n.plan} .kind=${t.kind} .q=${a} ?live=${i}></ca-task-table>`;case`journal`:return A`<ca-journal-table .run=${t.run} .rows=${n.journal} .fresh=${e.fresh} .kind=${t.kind} .stop=${t.stop} .q=${a}></ca-journal-table>`;case`outputs`:return A`<ca-contracts .run=${t.run} .outputs=${n.outputs} .journal=${n.journal} .plan=${n.plan}></ca-contracts>`;case`definitions`:return A`<ca-definitions .client=${this.store.client} .run=${t.run} .journal=${n.journal} .plan=${n.plan} .live=${i}
          .selected=${t.def}></ca-definitions>`;case`procs`:return A`<ca-procs-view .procs=${n.procs}></ca-procs-view>`;case`stream`:return A`<ca-task-view .client=${this.store.client} .journal=${n.journal} .plan=${n.plan} base-url=${this.baseUrl} .run=${t.run}
          .taskKey=${t.key??Er(n.tasks)} .view=${t.view} .round=${t.round} .live=${i}></ca-task-view>`;default:{let r=t.tab.slice(6);return A`<ca-panel-view .name=${r} .panel=${e.info.panels.find(e=>e.name===r)} .data=${n.panels[r]}></ca-panel-view>`}}}};U([V({attribute:`base-url`})],uc.prototype,`baseUrl`,void 0),U([V()],uc.prototype,`history`,void 0),U([V()],uc.prototype,`run`,void 0),U([V()],uc.prototype,`locale`,void 0),U([V({type:Boolean,reflect:!0})],uc.prototype,`live`,void 0),U([H()],uc.prototype,`snap`,void 0),U([H()],uc.prototype,`route`,void 0),U([H()],uc.prototype,`pickerOpen`,void 0),U([H()],uc.prototype,`qDraft`,void 0),U([kn(`main`)],uc.prototype,`main`,void 0),U([kn(`ca-toasts`)],uc.prototype,`toasts`,void 0),uc=U([B(`ca-monitor`),D()],uc);