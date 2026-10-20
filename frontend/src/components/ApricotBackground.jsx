import { useEffect, useRef } from 'react'
import {
  ACESFilmicToneMapping,
  AmbientLight,
  Box3,
  DirectionalLight,
  Group,
  HemisphereLight,
  PerspectiveCamera,
  Scene,
  Vector3,
  WebGLRenderer,
} from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

// Arka planda yavaşça dönen, sönük bir kayısı.
//
// Model: "Apricot fresh and cutted off fruit with leaf" — HQ3DMOD (model dosyasındaki
// info.json'a göre; lisans bilgisi dosyada yok). Dokular tools/optimize_gltf.py ile
// 4096 → 1024 px küçültülüp tek GLB'ye paketlenmiştir.
const MODEL_URL = `${import.meta.env.BASE_URL}models/apricot_cut.glb`
// Modelin en uzun kenarı sahnede bu boya ölçeklenir
const MODEL_SIZE = 2.6

function disposeObject(root) {
  root.traverse((obj) => {
    if (!obj.isMesh) return
    obj.geometry.dispose()
    const materials = Array.isArray(obj.material) ? obj.material : [obj.material]
    materials.forEach((m) => {
      Object.values(m).forEach((v) => v?.isTexture && v.dispose())
      m.dispose()
    })
  })
}

export default function ApricotBackground() {
  const hostRef = useRef(null)

  useEffect(() => {
    const host = hostRef.current
    let disposed = false
    const renderer = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.setClearColor(0x000000, 0)
    renderer.toneMapping = ACESFilmicToneMapping
    host.appendChild(renderer.domElement)

    const scene = new Scene()
    const camera = new PerspectiveCamera(35, 1, 0.1, 50)
    camera.position.set(0, 0, 6)

    scene.add(new AmbientLight(0xffffff, 0.5))
    scene.add(new HemisphereLight(0xfff1dc, 0x5a2a0a, 1.0))
    const key = new DirectionalLight(0xffffff, 2.4)
    key.position.set(3, 4, 5)
    scene.add(key)
    const rim = new DirectionalLight(0xffc27a, 1.2)
    rim.position.set(-4, -1, -3)
    scene.add(rim)

    // Model yüklenene kadar boş pivot; dönüş ve konum bu grup üzerinden yapılır
    const pivot = new Group()
    pivot.rotation.set(0.3, -0.6, 0.1)
    scene.add(pivot)
    const render = () => renderer.render(scene, camera)

    let model = null
    new GLTFLoader().load(
      MODEL_URL,
      (gltf) => {
        if (disposed) {
          disposeObject(gltf.scene)
          return
        }
        model = gltf.scene
        // Ortala ve boyutu normalize et
        const box = new Box3().setFromObject(model)
        const size = box.getSize(new Vector3())
        model.position.sub(box.getCenter(new Vector3()))
        const wrapper = new Group()
        wrapper.add(model)
        wrapper.scale.setScalar(MODEL_SIZE / Math.max(size.x, size.y, size.z))
        pivot.add(wrapper)
        render()
      },
      undefined,
      // Arka plan süsü; yüklenemezse arayüz etkilenmez
      (err) => console.warn('Kayısı modeli yüklenemedi:', err),
    )

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = host
      renderer.setSize(w, h, false)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      // Geniş ekranda sağa yaslanır; dar ekranda ortada durur
      const wide = camera.aspect > 1.1
      pivot.position.set(wide ? Math.min(1.9, camera.aspect * 0.95) : 0, wide ? -0.3 : 0.2, 0)
      pivot.scale.setScalar(wide ? 1 : 0.8)
      render()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(host)
    resize()

    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    let last = performance.now()
    const tick = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      pivot.rotation.y += dt * 0.16
      pivot.rotation.x = 0.3 + Math.sin(now / 5200) * 0.12
      render()
    }
    // Hareketi azalt açıksa ya da sekme görünmüyorsa animasyon durur (tek kare çizilir)
    const sync = () => {
      const run = !motion.matches && document.visibilityState === 'visible'
      last = performance.now()
      renderer.setAnimationLoop(run ? tick : null)
      if (!run) render()
    }
    sync()
    motion.addEventListener('change', sync)
    document.addEventListener('visibilitychange', sync)

    return () => {
      disposed = true
      renderer.setAnimationLoop(null)
      motion.removeEventListener('change', sync)
      document.removeEventListener('visibilitychange', sync)
      observer.disconnect()
      if (model) disposeObject(model)
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  return <div ref={hostRef} className="apricot-bg" aria-hidden="true" />
}
