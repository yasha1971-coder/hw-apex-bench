// Exercise real page logic in a minimal DOM; this is not a browser/layout test.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.listeners={};this.value='';this.style={setProperty(){}};this.textContent='';}
 append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
 setAttribute(k,v){this.attrs[k]=String(v);}
 replaceChildren(...ns){this.children=[];this.append(...ns);}
 addEventListener(k,fn){this.listeners[k]=fn;}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
 querySelectorAll(tag){return this.children.flatMap(c=>[...(c.tag===tag?[c]:[]),...c.querySelectorAll(tag)]);}
 querySelector(tag){return this.querySelectorAll(tag)[0];}
}
const html=fs.readFileSync(process.argv[2]||'.pages/index.html','utf8');
const data=JSON.parse(html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const els={};for(const m of html.matchAll(/<([a-z]+)[^>]*\bid="([^"]+)"[^>]*>/g)){els[m[2]]=new Element(m[1]);}
els.data.textContent=JSON.stringify(data);els.view.value='pair';els.profile.value='3';els.method.value='loop';
for(const id of ['values','batch','frontier','gpu']){els[id].append(new Element('thead'),new Element('tbody'));}
const context={document:{getElementById:id=>{assert(els[id],id);return els[id]},createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)},navigator:{},console};vm.createContext(context);vm.runInContext(html.split('<script>')[1].split('</script>')[0],context);
let combinations=0;
for(const profile of [0,1,2,3,4])for(const method of ['loop','batch'])for(const x of data.configs.length?['ratio','encode','decode','region_p50','region_p99','amplification','c_g','batch','h_alpha','break_even_n']:[])for(const y of ['ratio','encode','decode','region_p50','region_p99','amplification','c_g','batch','h_alpha','break_even_n']){
 els.profile.value=String(profile);els.method.value=method;els['x-axis'].value=x;els['y-axis'].value=y;vm.runInContext('paint()',context);
 for(const point of els.plot.querySelectorAll('circle'))assert(Number.isFinite(+point.attrs.cx)&&Number.isFinite(+point.attrs.cy));
 const cg=x==='c_g'||y==='c_g';assert.equal(els.values.querySelector('tbody').children.length,cg?15:4);
 assert.equal(els.batch.querySelector('tbody').children.length,8);
 combinations++;
}
els.view.value='parallel';vm.runInContext('paint()',context);assert(els.plot.querySelectorAll('polyline').length>0);
assert.equal(JSON.stringify(data),els.data.textContent);
console.log(combinations+' axis/profile/method combinations; finite plot coordinates; explicit missing rows; parallel view; data unchanged');
