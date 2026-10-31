import os
import io
import zipfile
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageOps

st.set_page_config(page_title="Extractor de Imágenes de PDF", page_icon="🖼️", layout="wide")

st.title("🖼️ Extractor de Imágenes Originales de PDF")
st.markdown("Extrae las imágenes **originales** tal cual están dentro del PDF, previsualízalas y descárgalas individualmente o en ZIP.")

# Función optimizada con caché para que la conversión a JPEG sea instantánea
@st.cache_data
def convertir_a_jpeg_optimizado(image_bytes):
    try:
        img_to_convert = Image.open(io.BytesIO(image_bytes))
        img_to_convert = ImageOps.exif_transpose(img_to_convert).convert("RGBA")
        fondo = Image.new("RGBA", img_to_convert.size, (255, 255, 255, 255))
        fondo.alpha_composite(img_to_convert)
        
        buffer_jpeg = io.BytesIO()
        fondo.convert("RGB").save(buffer_jpeg, "JPEG", quality=100, optimize=True, progressive=True)
        return buffer_jpeg.getvalue()
    except Exception:
        return None

# Subir archivo PDF
archivo_subido = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if archivo_subido is not None:
    # Procesar el PDF una sola vez y guardarlo en session_state
    if "current_pdf" not in st.session_state or st.session_state.get("pdf_name") != archivo_subido.name:
        with st.spinner("Extrayendo imágenes originales del PDF..."):
            ruta_pdf = os.path.join("/tmp", archivo_subido.name)
            with open(ruta_pdf, "wb") as f:
                f.write(archivo_subido.getbuffer())

            doc = fitz.open(ruta_pdf)
            image_records, xrefs = [], set()
            
            for num_pagina, pagina in enumerate(doc, start=1):
                imagenes = pagina.get_images(full=True)
                for info in imagenes:
                    xref = info[0]
                    if xref in xrefs:
                        continue
                    xrefs.add(xref)
                    try:
                        datos = doc.extract_image(xref)
                        if not datos or "image" not in datos:
                            continue
                        
                        ext = datos.get("ext", "bin")
                        ancho = datos.get("width", 0)
                        alto = datos.get("height", 0)
                        raw_bytes = datos["image"]
                        
                        image_records.append({
                            "pagina": num_pagina,
                            "bytes": raw_bytes,
                            "extension": ext,
                            "ancho": ancho,
                            "alto": alto
                        })
                    except Exception:
                        pass
            doc.close()
            
            st.session_state["image_records"] = image_records
            st.session_state["pdf_name"] = archivo_subido.name

    image_records = st.session_state.get("image_records", [])

    if not image_records:
        st.error("No se encontraron imágenes extraíbles en este PDF.")
    else:
        st.success(f"¡Extracción exitosa! Se encontraron {len(image_records)} imágenes originales.")

        # Selector de imágenes limpio
        opciones = [
            (i, f"Página {r['pagina']} — Imagen {i+1} ({r['ancho']}×{r['alto']} px) — Formato: {r['extension'].upper()}")
            for i, r in enumerate(image_records)
        ]
        
        seleccion_idx = st.selectbox(
            "Selecciona una imagen para previsualizar y descargar:",
            options=[o[0] for o in opciones],
            format_func=lambda x: dict(opciones)[x]
        )

        r = image_records[seleccion_idx]
        
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown(f"**Detalles originales:** Página {r['pagina']} | Resolución: {r['ancho']}×{r['alto']} px | Formato: `{r['extension'].upper()}`")
            try:
                with Image.open(io.BytesIO(r["bytes"])) as img:
                    st.image(img, caption=f"Página {r['pagina']}", use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo mostrar la vista previa: {e}")

        with col2:
            st.markdown("### Opciones de Descarga y Personalización")
            
            # Control de estado para el nombre fijado por cada imagen
            key_input = f"input_nombre_{seleccion_idx}"
            key_fijado = f"fijado_{seleccion_idx}"
            
            if key_input not in st.session_state:
                st.session_state[key_input] = f"imagen_pag_{r['pagina']}"
            if key_fijado not in st.session_state:
                st.session_state[key_fijado] = f"imagen_pag_{r['pagina']}"

            # Caja de texto y botón de fijar
            nombre_input = st.text_input("Nombre para el archivo (sin extensión):", key=key_input)
            
            if st.button("💾 Fijar este nombre", use_container_width=True):
                st.session_state[key_fijado] = nombre_input
                st.rerun()

            nombre_final = st.session_state[key_fijado].strip() if st.session_state[key_fijado] else "imagen"
            st.info(f"Nombre activo para descarga: **{nombre_final}**")

            # 1. Camino 1: Descargar el archivo ORIGINAL con el nombre fijado
            nombre_con_extension = f"{nombre_final}.{r['extension']}"
            st.download_button(
                label=f"📥 1. Descargar Original ({r['extension'].upper()})",
                data=r["bytes"],
                file_name=nombre_con_extension,
                mime=f"image/{r['extension']}",
                use_container_width=True
            )

            # 2. Camino 2: Descargar como JPEG con caché (Fondo blanco, calidad 100)
            jpeg_bytes = convertir_a_jpeg_optimizado(r["bytes"])
            if jpeg_bytes:
                st.download_button(
                    label="🖼️ 2. Descargar como JPEG (Fondo blanco, calidad 100)",
                    data=jpeg_bytes,
                    file_name=f"{nombre_final}.jpeg",
                    mime="image/jpeg",
                    use_container_width=True
                )
            else:
                st.error("No se pudo preparar la versión JPEG.")

        st.markdown("---")
        
        # 3. Camino 3: Descargar todas en ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, rec in enumerate(image_records, 1):
                zf.writestr(f"imagen_{idx:04d}.{rec['extension']}", rec["bytes"])
        
        st.download_button(
            label="📦 3. Descargar todas las imágenes originales en un archivo ZIP",
            data=zip_buffer.getvalue(),
            file_name="imagenes_originales_pdf.zip",
            mime="application/zip",
            use_container_width=True
        )
