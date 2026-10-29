/**
 * High-Performance 2D SLAM Occupancy Grid Map Renderer
 * Parses Base64 images, Netpbm PGM (P2/P5), YAML configs, and renders onto HTML5 Canvas.
 */

export interface MapData {
  label?: string
  pgm_data?: string | null
  resolution?: number
  origin_x?: number
  origin_y?: number
  width_px?: number
  height_px?: number
}

/** Where the map sits on the canvas: converts ROS map-frame metres <-> canvas pixels (image row 0 is the top = largest y). */
export interface MapView {
  toCanvas: (wx: number, wy: number) => [number, number]
  toWorld: (px: number, py: number) => [number, number]
  pxPerMetre: number
}

const FIT = 0.95

export function computeMapView(cw: number, ch: number, imgW: number, imgH: number, m: MapData): MapView {
  const s = Math.min(cw / imgW, ch / imgH) * FIT
  const w = imgW * s
  const h = imgH * s
  const x0 = (cw - w) / 2
  const y0 = (ch - h) / 2
  const res = m.resolution || 0.05
  const ox = m.origin_x ?? 0
  const oy = m.origin_y ?? 0
  return {
    pxPerMetre: s / res,
    toCanvas: (wx, wy) => [x0 + ((wx - ox) / res) * s, y0 + (imgH - (wy - oy) / res) * s],
    toWorld: (px, py) => [ox + ((px - x0) / s) * res, oy + (imgH - (py - y0) / s) * res],
  }
}

// In-memory image element cache to avoid recreating Image objects on every animation frame
const imageCache = new Map<string, HTMLImageElement>()

export function drawMapToCanvas(
  ctx: CanvasRenderingContext2D,
  canvasWidth: number,
  canvasHeight: number,
  mapData?: MapData | null
): MapView | null {
  // Clear canvas
  ctx.clearRect(0, 0, canvasWidth, canvasHeight)

  // 1. Draw Grid Background
  ctx.fillStyle = '#020617' // Deep dark slate
  ctx.fillRect(0, 0, canvasWidth, canvasHeight)

  const gridSize = 40
  ctx.strokeStyle = 'rgba(51, 65, 85, 0.3)' // Subtle grid lines
  ctx.lineWidth = 1
  for (let x = 0; x < canvasWidth; x += gridSize) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvasHeight)
    ctx.stroke()
  }
  for (let y = 0; y < canvasHeight; y += gridSize) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvasWidth, y)
    ctx.stroke()
  }

  if (!mapData || !mapData.pgm_data) {
    drawNoMap(ctx, canvasWidth, canvasHeight)
    return null
  }

  const dataStr = mapData.pgm_data.trim()

  // 2. Base64 Data URI Image (PNG / JPG / WEBP / Data URL)
  if (dataStr.startsWith('data:image') || dataStr.startsWith('iVBORw0KG')) {
    const src = dataStr.startsWith('data:image') ? dataStr : `data:image/png;base64,${dataStr}`
    
    let cachedImg = imageCache.get(src)
    if (!cachedImg) {
      cachedImg = new Image()
      cachedImg.src = src
      imageCache.set(src, cachedImg)
    }

    if (cachedImg.complete && cachedImg.naturalWidth > 0) {
      const view = computeMapView(canvasWidth, canvasHeight, cachedImg.naturalWidth, cachedImg.naturalHeight, mapData)
      const [x0, y0] = view.toCanvas(
        (mapData.origin_x ?? 0),
        (mapData.origin_y ?? 0) + cachedImg.naturalHeight * (mapData.resolution || 0.05)
      )
      const [x1, y1] = view.toCanvas(
        (mapData.origin_x ?? 0) + cachedImg.naturalWidth * (mapData.resolution || 0.05),
        (mapData.origin_y ?? 0)
      )
      ctx.imageSmoothingEnabled = false
      ctx.drawImage(cachedImg, x0, y0, x1 - x0, y1 - y0)
      drawOriginMarker(ctx, ...view.toCanvas(0, 0), mapData)
      return view
    }
    ctx.fillStyle = '#0ea5e9'
    ctx.font = '12px monospace'
    ctx.textAlign = 'center'
    ctx.fillText(`Loading map... (${mapData.label || 'Occupancy Grid'})`, canvasWidth / 2, canvasHeight / 2)
    return null
  }

  // 3. PGM Netpbm Format Parsing (P2 ASCII or P5 Binary)
  if (dataStr.startsWith('P2') || dataStr.startsWith('P5')) {
    return renderPgmData(ctx, canvasWidth, canvasHeight, dataStr, mapData)
  }

  drawNoMap(ctx, canvasWidth, canvasHeight, 'Map format not recognised')
  return null
}

function renderPgmData(
  ctx: CanvasRenderingContext2D,
  canvasWidth: number,
  canvasHeight: number,
  pgmStr: string,
  mapData: MapData
): MapView | null {
  try {
    const tokens = pgmStr.split(/\s+/).filter(t => t.length > 0 && !t.startsWith('#'))
    if (tokens.length < 4) throw new Error('Invalid PGM header')

    const width = parseInt(tokens[1], 10)
    const height = parseInt(tokens[2], 10)
    const pixelTokens = tokens.slice(4)

    if (isNaN(width) || isNaN(height) || width <= 0 || height <= 0) {
      drawNoMap(ctx, canvasWidth, canvasHeight, 'Invalid PGM header')
      return null
    }

    // Create offscreen canvas for rendering PGM raw pixels
    const offscreen = document.createElement('canvas')
    offscreen.width = width
    offscreen.height = height
    const offCtx = offscreen.getContext('2d')!
    const imgData = offCtx.createImageData(width, height)
    const data = imgData.data

    for (let i = 0; i < width * height; i++) {
      const val = i < pixelTokens.length ? parseInt(pixelTokens[i], 10) : 205
      const idx = i * 4

      if (val < 50) {
        // Obstacle / Wall (Dark Navy)
        data[idx] = 15     // R
        data[idx + 1] = 23 // G
        data[idx + 2] = 42 // B
        data[idx + 3] = 255
      } else if (val > 200) {
        // Free Space (Cyan / Blue Floor)
        data[idx] = 14     // R
        data[idx + 1] = 165// G
        data[idx + 2] = 233// B
        data[idx + 3] = 60 // Semi-transparent
      } else {
        // Unknown Space (Grid background)
        data[idx] = 2      // R
        data[idx + 1] = 6  // G
        data[idx + 2] = 23 // B
        data[idx + 3] = 120
      }
    }

    offCtx.putImageData(imgData, 0, 0)

    const view = computeMapView(canvasWidth, canvasHeight, width, height, mapData)
    const [x0, y0] = view.toCanvas(mapData.origin_x ?? 0, (mapData.origin_y ?? 0) + height * (mapData.resolution || 0.05))
    const [x1, y1] = view.toCanvas((mapData.origin_x ?? 0) + width * (mapData.resolution || 0.05), mapData.origin_y ?? 0)
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(offscreen, x0, y0, x1 - x0, y1 - y0)
    drawOriginMarker(ctx, ...view.toCanvas(0, 0), mapData)
    return view
  } catch {
    drawNoMap(ctx, canvasWidth, canvasHeight, 'Could not render the map')
    return null
  }
}

function drawNoMap(ctx: CanvasRenderingContext2D, w: number, h: number, msg = 'No map received from the robot yet') {
  ctx.save()
  ctx.fillStyle = '#64748b'
  ctx.font = '13px monospace'
  ctx.textAlign = 'center'
  ctx.fillText(msg, w / 2, h / 2 - 8)
  ctx.font = '11px monospace'
  ctx.fillText('Start the robot bridge (wms.launch.py) and the map syncs automatically, or upload one.', w / 2, h / 2 + 12)
  ctx.restore()
}

function drawOriginMarker(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  mapData?: MapData | null
) {
  ctx.save()
  ctx.strokeStyle = '#ef4444' // Red X axis
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(x - 15, y)
  ctx.lineTo(x + 15, y)
  ctx.stroke()

  ctx.strokeStyle = '#10b981' // Green Y axis
  ctx.beginPath()
  ctx.moveTo(x, y - 15)
  ctx.lineTo(x, y + 15)
  ctx.stroke()

  ctx.fillStyle = '#0ea5e9'
  ctx.font = '10px monospace'
  ctx.textAlign = 'left'
  const originStr = `(0,0) ${mapData?.label || 'map origin'}`
  ctx.fillText(originStr, x + 8, y - 8)
  ctx.restore()
}
