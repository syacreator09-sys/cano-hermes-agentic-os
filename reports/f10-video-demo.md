# F10 — Video demo Prometeo (StarHome OS)

Video de identidad/arquitectura, ~15-17s, generado 100% local y sin gasto.
Presenta las 7 oficinas nativas de StarHome (`governance`, `content`,
`engineering`, `research`, `operations`, `forge`=Prometeo, `finance`) y las
4 oficinas Docker planeadas para F11 (`office-ugc`, `office-content`,
`office-publish`, `office-analytics`, marcadas "en construcción"). No es un
demo funcional de las oficinas Docker — F11 las construye después.

## 1. Video final

- Repo (tracked, gitignored binario): `reports/media/starhome-prometeo-f10.mp4`
- Audio narración (tracked, gitignored binario): `reports/media/narracion-f10.mp3`
- `reports/media/` está en `.gitignore` — solo este `.md` y el reporte de
  `ffprobe` quedan en el commit.
- Origen del render: `~/dev-scratch/remotion-test/out/starhome-prometeo.mp4`

## 2. Resultado de ffprobe

Reporte completo: `reports/f10-video-demo-ffprobe.txt`

Resumen:

| Campo | Valor |
|---|---|
| Formato | MP4 (QuickTime/MOV, `isom`) |
| Duración | 17.00s (video) / 17.045s (audio) |
| Resolución | 1280x720 (720p, 16:9) |
| Video codec | H.264 (`avc1`, High profile, level 3.1) |
| FPS | 30/1 |
| Audio codec | AAC-LC, 48kHz, estéreo |
| Tamaño | 1.29 MB |
| Bitrate total | ~605 kb/s |
| `probe_score` | 100 (sin corrupción) |

Verificación de integridad adicional: `ffmpeg -v error -i starhome-prometeo-f10.mp4 -f null -`
terminó sin errores ni warnings (decodificación completa limpia, exit 0).

Nota de duración: el guión narrado dura 16.44s; el video final es de 17.00s
porque se añadió ~0.6s de "hold" al cierre (logo + tagline) para que el outro
no corte abruptamente. Está dentro del objetivo "~15s" pedido.

## 3. Composición Remotion y guión

- Proyecto Remotion (no copiado al repo, vive donde ya estaba inicializado):
  `~/dev-scratch/remotion-test`
  - `src/index.ts` — entry point (`registerRoot`)
  - `src/Root.tsx` — composición `Prometeo`, 1280x720, 30fps, 510 frames (17s)
  - `src/Demo.tsx` — animación: título de apertura, starfield generado por
    código (sin assets externos), grid de 7 chips de oficinas nativas
    apareciendo en secuencia sincronizada con la narración, transición a
    grid de 4 chips Docker (borde punteado + tag "DOCKER"), subtítulos
    (captions) con timing real, y outro con logo + tagline
  - `src/timeline.json` — timings derivados de faster-whisper (ver abajo)
  - `public/narracion.mp3` — copia del audio usado por el render (`<Audio>`)
- Guión de narración (español), texto completo (registrado aquí como fuente
  de verdad; también copiado en `reports/media/guion-f10.txt`, gitignorado
  junto al resto de `reports/media/`):

  > "StarHome OS. Siete oficinas nativas: gobierno, contenido, ingeniería,
  > investigación, operaciones, finanzas, y Prometeo, la forja de agentes.
  > En construcción: cuatro oficinas Docker para UGC, contenido, publicación
  > y analítica."

- TTS: `edge-tts --voice es-MX-JorgeNeural --rate=+15%` (gratis, sin llave,
  requiere red pero sin costo) → `narracion.mp3` (16.44s).
- Subtítulos/timing: transcripción real con `faster-whisper` (modelo
  `small`, CPU, `int8`) sobre `narracion.mp3`, con `word_timestamps=True`.
  Los timestamps por palabra se usaron para:
  1. Generar un `.srt` con los timings reales de la narración.
  2. Construir `src/timeline.json`, que define en qué segundo exacto aparece
     cada chip de oficina en la animación (sincronizado a cuando la voz
     pronuncia esa oficina).

## 4. Render

```
cd ~/dev-scratch/remotion-test
nice -n 15 npx remotion render src/index.ts Prometeo out/starhome-prometeo.mp4 \
  --codec=h264 --crf=23 --concurrency=2
```

- `nice -n 15`: prioridad baja, para no saturar la máquina (4 núcleos, sin
  GPU dedicada — Chrome Headless Shell corre CPU-only).
- `--concurrency=2`: limita paralelismo del renderer a la mitad de núcleos
  disponibles.
- Render descargó una vez `Chrome Headless Shell` (~92MB, vía la propia
  Remotion, sin llave/costo) para el motor de rasterizado.

## 5. Problemas encontrados

- El guión inicial (35 palabras) daba ~22s de narración a rate normal de
  `edge-tts`; se ajustó a `--rate=+15%` y se recortó ligeramente el texto
  para acercarse a los ~15s pedidos, resultando en 16.44s.
- `faster-whisper` transcribió "Docker" como "daque" (error fonético
  esperable al ser palabra en inglés dentro de audio en español) — no afectó
  el uso real, porque los timestamps por palabra (no el texto transcrito) son
  lo que se usó para sincronizar la animación; el texto mostrado en pantalla
  y subtítulos se escribió a mano con la ortografía correcta.
- `npx remotion still ... output.png --frames=N` no es el comando correcto
  para un solo frame (da error "output directory cannot have an extension");
  el comando correcto es `npx remotion still ... output.png --frame=N`
  (singular). Se usó para verificar visualmente 4 frames clave antes del
  render final — sin este chequeo no se hubiera detectado que el header
  persistente se solapaba con el texto del outro (ya corregido en
  `Demo.tsx`, `HeaderBar` ahora recibe `hideFrom` y se desvanece antes del
  cierre).
- Sin problemas de dependencias: `edge-tts`, `faster-whisper`, Remotion,
  `ffprobe` y `nice` ya estaban disponibles en la máquina como se indicó.
- Cero llamadas de pago: `edge-tts` es gratis (requiere red, sin llave);
  `faster-whisper` corrió 100% local en CPU; Remotion renderizó 100% local
  en CPU. No se publicó el video en ningún sitio.
