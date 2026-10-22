type Point = { x: number; y: number; z: number };
type Particle = Point & { strength: number; phaseSin: number; phaseCos: number; column: number; screen: {x:number;y:number} };
const TAU = Math.PI * 2;
const ORIGIN: Point = {x:0,y:0,z:0};

/** A procedural email sculpture: source bytes, an envelope, and travelling delivery signals. */
export function createMailSignalRenderer(canvas: HTMLCanvasElement | OffscreenCanvas) {
  const ctx = canvas.getContext("2d") as CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null;
  if (!ctx) return null;

  let width = 1;
  let height = 1;
  let frame = 0;
  let disposed = false;
  let visible = true;
  let lastPaint = -Infinity;
  let frameInterval = 1000/60;
  let averageCost = 0;
  let expensiveFrames = 0;
  let cheapFrames = 0;
  let background: CanvasGradient;
  const particles: Particle[] = [];
  for (let y = -136; y <= 136; y += 10) {
    for (let x = -220; x <= 220; x += 10) {
      const seed = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
      const phase = x*.012+y*.018;
      particles.push({x,y,z:0,strength:.12+(seed-Math.floor(seed))*.32,phaseSin:Math.sin(phase),phaseCos:Math.cos(phase),column:(x+220)/10,screen:{x:0,y:0}});
    }
  }
  // At phone size the sculpture is only about 250px wide: keep subpixel detail out of its draw list.
  const compactParticles=particles.filter((particle,index)=>particle.column%2===0 && Math.floor(index/45)%2===0);
  const envelope = [
    [{x:-225,y:-140,z:0},{x:225,y:-140,z:0},{x:225,y:140,z:0},{x:-225,y:140,z:0},{x:-225,y:-140,z:0}],
    [{x:-225,y:-140,z:0},{x:0,y:26,z:5},{x:225,y:-140,z:0}],
    [{x:-225,y:140,z:0},{x:-72,y:-20,z:1}],
    [{x:225,y:140,z:0},{x:72,y:-20,z:1}],
  ];
  const front = envelope[0].slice(0,4);
  const back = front.map(p=>({...p,z:-35}));
  const illumination = new Float64Array(45);
  const buckets: Particle[][] = Array.from({length:16},()=>[]);
  const scratch = {x:0,y:0};
  const circle = (radius:number,start=0,end=TAU) => Array.from({length:73},(_,i)=>({x:Math.cos(start+(end-start)*i/72)*radius,y:Math.sin(start+(end-start)*i/72)*radius,z:0}));
  const lensRings = {back:circle(57),front:circle(55),inner:circle(49)};
  const arcTemplate = circle(59,0,1.15);
  const orbitPath = arcTemplate.map(p=>({...p}));
  const ridges = Array.from({length:8},(_,ridge)=>Array.from({length:77},(_,step)=>{
    const angle=-.28+(TAU-.54)*step/76;
    const organic=6+ridge*4.7+Math.sin(angle*3+ridge*.2)*1.4;
    return {x:Math.sin(angle)*organic*.77+Math.sin(angle*2)*2,y:Math.cos(angle)*organic,z:2};
  }));
  const routes = Array.from({length:6},(_,route)=>{
    const angle=route*TAU/6+.28;
    const cos=Math.cos(angle),sin=Math.sin(angle);
    const curve=(progress:number):Point=>({x:cos*(270+progress*280),y:sin*(160+progress*155)+Math.sin(progress*Math.PI)*(route%2?80:-65),z:-80-Math.sin(progress*Math.PI)*160});
    return {curve,path:Array.from({length:51},(_,step)=>curve(step/50)),end:curve(.83)};
  });

  function resize(rect: {width:number;height:number;pixelRatio:number}) {
    width = Math.max(1,rect.width);
    height = Math.max(1,rect.height);
    const ratio = Math.min(rect.pixelRatio || 1,width<621 ? 1 : 1.5,Math.sqrt(1_800_000/(width*height)));
    const pixelWidth=Math.round(width*ratio),pixelHeight=Math.round(height*ratio);
    if(canvas.width===pixelWidth && canvas.height===pixelHeight && background) return;
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
    ctx!.setTransform(ratio,0,0,ratio,0,0);
    const mobile=width<621;
    const scale=Math.min(width*(mobile ? .82 : .43)/520,height*(mobile ? .49 : .77)/470);
    const cx=width*(mobile ? .59 : .755),cy=height*(mobile ? .31 : .53);
    background=ctx!.createRadialGradient(cx,cy,0,cx,cy,Math.max(1,380*scale));
    background.addColorStop(0,"rgba(42,104,167,.15)");
    background.addColorStop(.5,"rgba(30,71,121,.065)");
    background.addColorStop(1,"rgba(9,11,14,0)");
    schedule();
  }

  function schedule() {
    if(background && !disposed && visible && !frame) frame=requestAnimationFrame(paint);
  }

  function setVisible(next:boolean) {
    if(disposed) return;
    visible=next;
    if(!visible) {cancelAnimationFrame(frame);frame=0;}
    else {lastPaint=-Infinity;schedule();}
  }

  function paint(milliseconds: number) {
    frame=0;
    if(disposed || !visible) return;
    if(milliseconds-lastPaint < frameInterval-.5) {schedule();return;}
    lastPaint=milliseconds;
    const started=performance.now();
    const time = milliseconds / 1000;
    const mobile = width < 621;
    const compact = mobile || averageCost>8;
    const cx = width * (mobile ? .59 : .755);
    const cy = height * (mobile ? .31 : .53);
    const scale = Math.min(width * (mobile ? .82 : .43) / 520,height * (mobile ? .49 : .77) / 470);
    const yaw = -.32 + Math.sin(time * .22) * .1;
    const pitch = .15 + Math.cos(time * .18) * .045;
    const roll = -.075 + Math.sin(time * .16) * .025;
    const cosYaw=Math.cos(yaw),sinYaw=Math.sin(yaw),cosPitch=Math.cos(pitch),sinPitch=Math.sin(pitch),cosRoll=Math.cos(roll),sinRoll=Math.sin(roll);
    const float=Math.sin(time*.35)*5;
    const project = (point:Point,offset:Point=ORIGIN,out=scratch) => {
      const x=point.x+offset.x,y=point.y+offset.y,z=point.z+offset.z;
      const rx = x*cosYaw+z*sinYaw;
      const rz = -x*sinYaw+z*cosYaw;
      const ry = y*cosPitch-rz*sinPitch;
      const depth = y*sinPitch+rz*cosPitch;
      const perspective = 1000 / (1000 + depth);
      out.x=cx+(rx*cosRoll-ry*sinRoll)*scale*perspective;
      out.y=cy+(rx*sinRoll+ry*cosRoll)*scale*perspective+float;
      return out;
    };
    ctx!.clearRect(0,0,width,height);
    ctx!.fillStyle = background;
    ctx!.fillRect(0,0,width,height);

    const stroke = (points:Point[],color:string,lineWidth=1,offset=ORIGIN) => {
      ctx!.beginPath();
      for(let index=0;index<points.length;index+=compact && points.length>24 ? 2 : 1) {
        const p = project(points[index],offset);
        if(index===0) ctx!.moveTo(p.x,p.y); else ctx!.lineTo(p.x,p.y);
      }
      ctx!.strokeStyle = color;
      ctx!.lineWidth = lineWidth;
      ctx!.stroke();
    };
    const dot = (point:Point,radius:number,color:string) => {
      const p = project(point);
      ctx!.beginPath();
      ctx!.arc(p.x,p.y,Math.max(.1,radius * scale),0,TAU);
      ctx!.fillStyle = color;
      ctx!.fill();
    };
    const surface = (points:Point[],top:string,bottom:string,edge="rgba(156,203,239,.2)",offset=ORIGIN) => {
      let left=Infinity,right=-Infinity,upper=Infinity,lower=-Infinity;
      ctx!.beginPath();
      for(let i=0;i<points.length;i++) {
        const p=project(points[i],offset);
        left=Math.min(left,p.x);right=Math.max(right,p.x);upper=Math.min(upper,p.y);lower=Math.max(lower,p.y);
        if(i===0) ctx!.moveTo(p.x,p.y); else ctx!.lineTo(p.x,p.y);
      }
      const material = ctx!.createLinearGradient(left,upper,right,lower);
      material.addColorStop(0,top);
      material.addColorStop(1,bottom);
      ctx!.closePath();
      ctx!.fillStyle = material;
      ctx!.fill();
      ctx!.strokeStyle = edge;
      ctx!.lineWidth = .8;
      ctx!.stroke();
    };

    // Continuous curved routes place the message inside a larger delivery network.
    for (let route=0;route<6;route++) {
      const {path,curve,end}=routes[route];
      stroke(path,"rgba(119,158,205,.11)",.75);
      dot(end,3,"rgba(153,196,237,.45)");
      const packets=compact ? 2 : 3;
      for(let packet=0;packet<packets;packet++) {
        const progress = (time * .075 + packet / packets + route * .13) % 1;
        const head = curve(progress);
        stroke([curve(Math.max(0,progress-.045)),head],"rgba(150,211,255,.6)",1.4);
        dot(head,1.8,"rgba(199,231,255,.9)");
      }
    }

    // Layered source sheets, with an actual folded corner, sit inside the open top edge.
    const lift = Math.sin(time * .45) * 7;
    for(let layer=1;layer>=0;layer--) {
      const x = layer*13;
      const y = lift-layer*12;
      const z = -42-layer*17;
      surface([
        {x:-155+x,y:-209+y,z},{x:126+x,y:-209+y,z},
        {x:154+x,y:-182+y,z},{x:154+x,y:37+y,z},{x:-155+x,y:37+y,z},
      ],layer?"rgba(74,109,145,.09)":"rgba(120,166,206,.16)","rgba(20,37,58,.76)","rgba(154,198,232,.3)");
      if(layer===0) {
        surface([{x:126,y:-209+y,z},{x:126,y:-182+y,z},{x:154,y:-182+y,z}],"rgba(193,221,242,.25)","rgba(58,94,128,.12)");
        for(let line=0;line<4;line++) {
          const lineY = -184+line*14+y;
          stroke([{x:-128,y:lineY,z:z+1},{x:line===0?35:114-line*8,y:lineY,z:z+1}],"rgba(174,214,243,.3)",line===0?1.5:.8);
        }
      }
    }

    // Satin face panels and bevelled depth replace the original flat wireframe.
    surface([back[1],back[2],front[2],front[1]],"rgba(65,106,148,.6)","rgba(10,21,35,.95)");
    surface([back[2],back[3],front[3],front[2]],"rgba(29,60,94,.9)","rgba(12,23,38,.98)");
    surface(front,"rgba(25,48,75,.92)","rgba(8,19,33,.98)","rgba(183,219,246,.4)");
    surface([front[0],{x:0,y:24,z:5},front[3]],"rgba(56,88,120,.3)","rgba(15,33,55,.18)");
    surface([front[1],front[2],{x:0,y:24,z:5}],"rgba(76,113,151,.14)","rgba(16,35,58,.5)");
    surface([front[3],{x:0,y:-18,z:8},front[2]],"rgba(48,83,119,.35)","rgba(12,29,48,.74)");
    surface([front[0],front[1],{x:0,y:26,z:12}],"rgba(70,109,146,.25)","rgba(17,36,57,.78)","rgba(174,216,247,.4)");
    stroke([{x:-216,y:-134,z:1},{x:216,y:-134,z:1}],"rgba(201,231,253,.35)",.7);
    stroke([{x:-216,y:134,z:2},{x:216,y:134,z:2}],"rgba(141,194,235,.17)",.7);

    const scan = Math.sin(time * .62) * 265;
    for(let column=0;column<45;column++) illumination[column]=Math.exp(-Math.pow((-220+column*10-scan)/34,2));
    for(const bucket of buckets) bucket.length=0;
    const shimmerSin=Math.sin(time*1.5),shimmerCos=Math.cos(time*1.5);
    for(const particle of compact ? compactParticles : particles) {
      const shine=illumination[particle.column];
      const shimmer=.82+(shimmerSin*particle.phaseCos+shimmerCos*particle.phaseSin)*.18;
      const alpha=Math.min(.75,particle.strength*shimmer*.5+shine*.5);
      project(particle,ORIGIN,particle.screen);
      buckets[Math.min(15,Math.floor(alpha/.75*16))].push(particle);
    }
    // Quantized opacity preserves the light pass while sharing sixteen paint operations.
    for(let index=0;index<buckets.length;index++) {
      if(!buckets[index].length) continue;
      ctx!.beginPath();
      for(const particle of buckets[index]) {
        const radius=Math.max(.1,(.7+illumination[particle.column]*.65)*scale);
        ctx!.rect(particle.screen.x-radius,particle.screen.y-radius,radius*2,radius*2);
      }
      ctx!.fillStyle=`rgba(149,204,246,${(index+.5)*.75/16})`;
      ctx!.fill();
    }
    // The fold lines and a travelling light pass keep the silhouette legible throughout the loop.
    envelope.forEach(points=>stroke(points,"rgba(105,191,255,.07)",4));
    envelope.forEach((points,index)=>stroke(points,index===0?"rgba(182,223,252,.72)":"rgba(166,213,249,.82)",index===0?1.35:1.1));
    const scanX = Math.max(-224,Math.min(224,scan));
    const scanAlpha = Math.max(0,1-Math.abs(scan)/265) * .24;
    stroke([{x:scanX,y:-138,z:2},{x:scanX,y:138,z:2}],`rgba(200,235,255,${scanAlpha})`,2);

    // A floating inspection lens resolves a fabricated ridge field in the message surface.
    const lens = {x:125,y:62,z:52+Math.sin(time*.4)*3};
    const stem = [{x:lens.x+36,y:lens.y+36,z:lens.z},{x:lens.x+76,y:lens.y+76,z:lens.z}];
    stroke(stem,"rgba(11,21,34,.98)",11*scale);
    stroke(stem,"rgba(124,166,205,.36)",6*scale);
    stroke(stem.map(p=>({...p,x:p.x-1,z:p.z+2})),"rgba(191,221,245,.4)",1.2*scale);
    surface(lensRings.back,"rgba(63,94,126,.6)","rgba(12,23,38,.95)","rgba(151,196,230,.35)",{...lens,z:lens.z-7});
    surface(lensRings.front,"rgba(28,52,76,.97)","rgba(7,20,34,.98)","rgba(188,223,248,.72)",lens);
    stroke(lensRings.inner,"rgba(122,186,232,.22)",.7,{...lens,z:lens.z+1});
    for(let ridge=0;ridge<8;ridge++) {
      const intensity = .29+Math.sin(time*.8+ridge*.4)*.1;
      stroke(ridges[ridge],`rgba(163,215,251,${intensity})`,.85,lens);
    }
    const lensScan = Math.sin(time*.8)*39;
    const chord = Math.sqrt(42*42-lensScan*lensScan);
    stroke([{x:lens.x-chord,y:lens.y+lensScan,z:lens.z+3},{x:lens.x+chord,y:lens.y+lensScan,z:lens.z+3}],"rgba(186,230,255,.38)",.8);
    const orbit = time*.33;
    const cosOrbit=Math.cos(orbit),sinOrbit=Math.sin(orbit);
    for(let i=0;i<orbitPath.length;i++) {
      orbitPath[i].x=arcTemplate[i].x*cosOrbit-arcTemplate[i].y*sinOrbit;
      orbitPath[i].y=arcTemplate[i].x*sinOrbit+arcTemplate[i].y*cosOrbit;
      orbitPath[i].z=1;
    }
    stroke(orbitPath,"rgba(188,228,255,.8)",1.35,lens);
    dot({x:lens.x+Math.cos(orbit+1.15)*59,y:lens.y+Math.sin(orbit+1.15)*59,z:lens.z+2},1.7,"rgba(220,242,255,.95)");

    // Byte particles drift through the scene without adding decorative UI labels.
    for(let index=0;index<(compact ? 38 : 76);index++) {
      const progress = (time * .022 + index * .61803398875) % 1;
      const x = -590 + progress * 1180;
      const y = Math.sin(index * 2.4) * 300 + Math.sin(time * .22 + index) * 12;
      dot({x,y,z:Math.cos(index)*140-80},index%6===0?1.2:.65,`rgba(129,181,227,${.12+Math.sin(progress*Math.PI)*.25})`);
    }
    const cost=performance.now()-started;
    averageCost=averageCost*.9+cost*.1;
    expensiveFrames=averageCost>8?expensiveFrames+1:0;
    cheapFrames=averageCost<4?cheapFrames+1:0;
    if(cost>16 || expensiveFrames>10) frameInterval=1000/30;
    if(cheapFrames>120) frameInterval=1000/60;
    schedule();
  }

  return {resize,setVisible,dispose() {
    disposed = true;
    cancelAnimationFrame(frame);
    ctx.clearRect(0,0,width,height);
  }};
}
