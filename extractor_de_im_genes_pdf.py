import streamlit as st
import os
import shutil
import zipfile
from PIL import Image, ImageOps
import fitz  # PyMuPDF

# Configuración de la página
st.set_page_config(
    page_title="Extractor de Imágenes de PDF",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para una interfaz moderna y amigable
st.markdown("""
    <style>
    .main {
        background-color: #f8fafc;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.2s ease;
    }
    .stDownloadButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
    }
    .card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Título principal y descripción amigable
st.title("📄 Extractor Profesional de Imágenes de PDF")
st.markdown("Sube cualquier documento PDF para extraer, previsualizar y descargar todas las imágenes incrustadas de forma limpia y rápida.")

# Carpeta temporal de trabajo
CARPETA_SALIDA = "imagenes_extraidas_temp"

def limpiar_directorio():
    if os.path.exists(CARPETA_SALIDA):
        shutil.rmtree(CARPETA_SALIDA)
    os.makedirs(CARPETA_SALIDA, exist_ok=True)

# Barra lateral para carga de archivos y opciones
with st.sidebar:
    st.header("1. Subir Archivo")
    archivo_subido = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])
    
    st.markdown("---")
    st.info("💡 **Consejo:** El procesamiento es completamente privado y seguro en tu sesión actual.")

if archivo_subido is not None:
    # Guardar archivo PDF temporalmente
    ruta_pdf_temporal = "temp_uploaded.pdf"
    with open(ruta_pdf_temporal, "wb") as f:
        f.write(archivo_subido.getbuffer())

    # Botón o disparador de extracción
    if "imagenes_procesadas" not in st.session_state or st.session_state.get("archivo_actual") != archivo_subido.name:
        limpiar_directorio()
        
        with st.spinner("⏳ Analizando PDF y extrayendo imágenes... Por favor espera."):
            try:
                doc = fitz.open(ruta_pdf_temporal)
                image_records = []
                xrefs = set()
                errores = 0

                for num_pagina, pagina in enumerate(doc, start=1):
                    imagenes = pagina.get_images(full=True)
                    for info in imagenes:
                        xref = info[0]
                        smask = info[1] if len(info) > 1 else 0
                        if xref in xrefs:
                            continue
                        xrefs.add(xref)
                        try:
                            datos = doc.extract_image(xref)
                            ext, ancho, alto = datos.get("ext", "bin"), datos.get("width", 0), datos.get("height", 0)
                            
                            if smask:
                                pix = fitz.Pixmap(doc, xref)
                                mascara = fitz.Pixmap(doc, smask)
                                combinado = fitz.Pixmap(pix, mascara)
                                nombre = f"imagen_{len(image_records)+1:04d}.png"
                                ruta = os.path.join(CARPETA_SALIDA, nombre)
                                combinado.save(ruta)
                                ext_final, ancho_final, alto_final = "png", combinado.width, combinado.height
                                del combinado, mascara, pix
                            else:
                                nombre = f"imagen_{len(image_records)+1:04d}.{ext}"
                                ruta = os.path.join(CARPETA_SALIDA, nombre)
                                with open(ruta, "wb") as f_img:
                                    f_img.write(datos["image"])
                                ext_final, ancho_final, alto_final = ext, ancho, alto
                                
                            image_records.append({
                                "id": len(image_records) + 1,
                                "pagina": num_pagina,
                                "ruta": ruta,
                                "nombre": nombre,
                                "extension": ext_final,
                                "ancho": ancho_final,
                                "alto": alto_final,
                                "smask": bool(smask)
                            })
                        except Exception:
                            errores += 1
                doc.close()

                st.session_state["image_records"] = image_records
                st.session_state["archivo_actual"] = archivo_subido.name
                st.session_state["imagenes_procesadas"] = True

            except Exception as e:
                st.error(f"❌ Ocurrió un error al procesar el PDF: {e}")

    # Si ya tenemos imágenes extraídas, mostramos la interfaz principal
    if st.session_state.get("imagenes_procesadas") and st.session_state["image_records"]:
        image_records = st.session_state["image_records"]
        
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.metric("📁 Archivo", archivo_subido.name)
        with col_info2:
            st.metric("🖼️ Imágenes Únicas Encontradas", len(image_records))
        with col_info3:
            # Crear ZIP general descargable
            ruta_zip = "imagenes_extraidas.zip"
            with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for r in image_records:
                    zf.write(r["ruta"], arcname=r["nombre"])
            
            with open(ruta_zip, "rb") as f_zip:
                st.download_button(
                    label="📦 Descargar Todas (ZIP)",
                    data=f_zip,
                    file_name="imagenes_pdf_extraidas.zip",
                    mime="application/zip",
                    use_container_width=True
                )

        st.markdown("---")
        
        # Selector y Galería Interactiva
        st.subheader("🔍 Explorador y Vista Previa de Imágenes")
        
        # Opciones para el selector desplegable
        opciones_selector = {
            f"Imagen {r['id']} (Pág. {r['pagina']}) — {r['ancho']}x{r['alto']} px [{r['extension'].upper()}]": r
            for r in image_records
        }
        
        seleccion_str = st.selectbox("Selecciona una imagen para inspeccionar:", list(opciones_selector.keys()))
        img_seleccionada = opciones_selector[seleccion_str]
        
        # Diseño de dos columnas para previsualización y acciones detalladas
        col_prev, col_acciones = st.columns([1.5, 1])
        
        with col_prev:
            st.markdown(f"#### Vista Previa (Página {img_seleccionada['pagina']})")
            try:
                img_pil = Image.open(img_seleccionada["ruta"])
                st.image(img_pil, use_container_width=True, caption=f"Dimensiones: {img_seleccionada['ancho']} x {img_seleccionada['alto']} px")
            except Exception as e:
                st.error("No se pudo cargar la vista previa de esta imagen.")

        with col_acciones:
            st.markdown("#### ⚙️ Opciones de Descarga")
            st.write(f"**Formato Original:** `{img_seleccionada['extension'].upper()}`")
            if img_seleccionada['smask']:
                st.caption("✨ Contiene transparencia combinada automáticamente.")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Botón 1: Descargar original
            with open(img_seleccionada["ruta"], "rb") as file_orig:
                st.download_button(
                    label="⬇️ Descargar Imagen Original",
                    data=file_orig,
                    file_name=img_seleccionada["nombre"],
                    mime=f"image/{img_seleccionada['extension']}",
                    use_container_width=True
                )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Botón 2: Convertir y descargar en JPG con fondo blanco
            base_nombre = os.path.splitext(img_seleccionada["nombre"])[0]
            nombre_jpg = f"{base_nombre}_fondo_blanco.jpg"
            
            # Procesar imagen a JPG con fondo blanco
            with Image.open(img_seleccionada["ruta"]) as img_conv:
                img_conv = ImageOps.exif_transpose(img_conv).convert("RGBA")
                fondo = Image.new("RGBA", img_conv.size, (255, 255, 255, 255))
                fondo.alpha_composite(img_conv)
                
                import io
                buffer_jpg = io.BytesIO()
                fondo.convert("RGB").save(buffer_jpg, "JPEG", quality=90, optimize=True)
                buffer_jpg.seek(0)
                
                st.download_button(
                    label="🖼️ Descargar en JPG (Fondo Blanco)",
                    data=buffer_jpg,
                    file_name=nombre_jpg,
                    mime="image/jpeg",
                    use_container_width=True
                )

    elif st.session_state.get("imagenes_procesadas") and not st.session_state["image_records"]:
        st.warning("⚠️ No se encontraron imágenes extraíbles en este archivo PDF.")

else:
    # Pantalla de bienvenida amigable cuando no hay archivo cargado
    st.markdown("""
        <div style="text-align: center; padding: 3rem; background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
            <h3>👋 ¡Bienvenido!</h3>
            <p style="color: #64748b;">Para comenzar, sube un archivo PDF usando el panel lateral izquierdo.</p>
            <p style="color: #94a3b8; font-size: 0.9rem;">El sistema extraerá automáticamente todas las imágenes originales conservando la máxima calidad, con soporte para transparencias y conversión instantánea.</p>
        </div>
    """, unsafe_allow_html=True)