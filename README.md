# Caso práctico · Fábrica de IA y Automatización · ESIC Medellín

**Henry Taborda** · septiembre de 2026

- Demo desplegado: https://agora-esic.vercel.app
- Demo extendido con video: https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7
- Video narrado: [video/Demo_Fabrica_IA_Henry_Taborda.mp4](video/Demo_Fabrica_IA_Henry_Taborda.mp4)
- Guía paso a paso: [`codigo/GUIA_DEMO.md`](codigo/GUIA_DEMO.md)

| Carpeta / archivo | Contenido |
|---|---|
| `01` … `05` (PDF) | Los cinco entregables del caso |
| `NOTA_DE_DECISIONES.pdf` | Las decisiones detrás de la entrega |
| `codigo/` | Orquestador, validador, flujo n8n, modelo de ROI, demo ejecutable y 42 pruebas |
| `markdown/` | Fuentes de los documentos |
| `demo_web/` | Demo extendido para abrir localmente |
| `video/` | Video narrado del ejemplo de funcionamiento |
| `sitio/` | Demo extendido listo para desplegar en Vercel (`vercel --prod` desde esa carpeta) |

```bash
cd codigo
python demo.py
python modelo_roi.py
python -m unittest discover -s pruebas -t .
```
