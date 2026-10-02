'use client'

import { Html, Line, OrbitControls, PerspectiveCamera } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'

type Node = {id:string; label:string; path:string; language:string; degree?:number; module?:string}
type Edge = {source:string;target:string;kind:string}

function PolygonCore(){
  const ref = useRef<THREE.Mesh>(null)
  useFrame((_,delta)=>{ if(ref.current) ref.current.rotation.y += delta * 0.16 })
  return <mesh ref={ref} rotation={[0.28,0.1,0]}>
    <icosahedronGeometry args={[1.42,1]}/>
    <meshBasicMaterial color="#1D4533" transparent opacity={0.06} wireframe />
  </mesh>
}

export function ArchitectureScene({nodes,edges,interactive=false,showLabels=false}:{nodes:Node[];edges:Edge[];interactive?:boolean;showLabels?:boolean}){
  const shown = nodes.slice(0,32)
  const points = useMemo(() => {
    if(!shown.length) return [] as [number,number,number][]
    return shown.map((n,i) => {
      const high = (n.degree||0) >= 4
      const ring = high ? 0.72 : 1.25 + (i%3)*0.22
      const count = high ? Math.max(3, shown.filter(x=>(x.degree||0)>=4).length) : Math.max(6,shown.length)
      const highIndex = shown.slice(0,i).filter(x=>(x.degree||0)>=4).length
      const index = high ? highIndex : i
      const angle = (index / count) * Math.PI * 2
      const y = high ? (i%2 ? 0.32 : -0.32) : ((i%5)-2)*0.18
      return [Math.cos(angle)*ring, y, Math.sin(angle)*ring*0.72] as [number,number,number]
    })
  },[shown])
  const index = useMemo(()=>new Map(shown.map((n,i)=>[n.id,i])),[shown])
  return <div className="scene-wrap"><Canvas dpr={[1,1.6]}><PerspectiveCamera makeDefault position={[0,0,4.9]} fov={44}/><ambientLight intensity={1.7}/><directionalLight position={[3,4,5]} intensity={1.1}/><pointLight position={[-2,-2,2]} intensity={0.7}/><PolygonCore/>
    <mesh rotation={[Math.PI/2,0,0]}><torusGeometry args={[1.42,0.018,8,64]}/><meshBasicMaterial color="#F9D2BA" transparent opacity={0.58}/></mesh>
    {shown.map((n,i)=>{const hot=(n.degree||0)>=4;return <group key={n.id} position={points[i]}>
      <mesh scale={hot?1.18:1}><octahedronGeometry args={[0.12,0]}/><meshStandardMaterial color={hot?'#5E3122':'#1D4533'} roughness={0.35} metalness={0.35} emissive={hot?'#F9D2BA':'#F7EAE0'} emissiveIntensity={0.18}/></mesh>
      {showLabels && <Html center distanceFactor={7} style={{pointerEvents:'none'}}><div className={`scene-label ${hot?'hot':''}`}><strong>{n.label}</strong><span>{n.module || n.language}</span></div></Html>}
    </group>})}
    {edges.slice(0,70).map((e,i)=>{const a=index.get(e.source),b=index.get(e.target);if(a===undefined||b===undefined)return null;return <Line key={i} points={[points[a],points[b]]} color="#5E3122" transparent opacity={showLabels?.42:.24} lineWidth={showLabels?1.15:0.8}/>})}
    {interactive&&<OrbitControls enablePan={false} minDistance={3.3} maxDistance={8} enableDamping dampingFactor={0.08}/>}</Canvas></div>
}
