import os
import io
import zipfile
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageOps

st.set_page_config(page_title="Extractor de Imágenes de PDF", page_icon="🖼️", layout="wide")

st.title("🖼️ Extractor de Imágenes Originales de PDF")
st.markdown("Sube un PDF para extraer sus imágenes originales, previsualizarlas y descargarlas con nombre personalizado o en ZIP.")

# Subir archivo PDF
archivo_subido = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if archivo_subido is not None:
    # Procesar el PDF una sola vez y guardarlo en session_state para evitar lentitud
    if "current_pdf" not in st.session_state or st.session_state.get("pdf_name") != archivo_subido.name:
        with st.spinner("Leyendo y extrayendo imágenes originales del PDF..."):
            ruta_pdf = os.path.join("/tmp", archivo_subido.name)
            with open(ruta_pdf, "wb") as f:
                f.write(archivo_subido.getbuffer())

            doc = fitz.open(ruta_pdf)
            image_records, xrefs = [], set()
            
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
                            raw_bytes = combinado.tobytes("png")
                            ext_final, ancho_final, alto_final = "png", combinado.width, combinado.height
                            del combinado, mascara, pix
                        else:
                            raw_bytes = datos["image"]
                            ext_final, ancho_final, alto_final = ext, ancho, alto
                        
                        image_records.append({
                            "pagina": num_pagina,
                            "bytes": raw_bytes,
                            "extension": ext_final,
                            "ancho": ancho_final,
                            "alto": alto_final,
                            "smask": bool(smask)
                        })
                    except Exception:
                        pass
            doc.close()
            
            st.session_state["image_records"] = image_records
            st.session_state["pdf_name"] = archivo_subido.name
            st.session_state.pop("nombre_fijado", None)

    image_records = st.session_state.get("image_records", [])

    if not image_records:
        st.error("No se encontraron imágenes extraíbles en este PDF.")
    else:
        st.success(f"¡Extracción completada! Se encontraron {len(image_records)} imágenes originales.")

        # Selector de imágenes
        opciones = [
            (i, f"Página {r['pagina']} — {r['ancho']}×{r['alto']} — {r['extension'].upper()}" + (" (con transparencia)" if r["smask"] else ""))
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
                # Vista previa rápida desde memoria con BytesIO
                with Image.open(io.BytesIO(r["bytes"])) as img:
                    st.image(img, caption=f"Página {r['pagina']}", use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo mostrar la vista previa: {e}")

        with col2:
            st.markdown("### Opciones de Descarga Personalizada")
            
            # Inicializar estado del nombre personalizado
            sugerencia_inicial = f"imagen_pag_{r['pagina']}"
            if "nombre_fijado" not in st.session_state:
                st.session_state["nombre_fijado"] = sugerencia_inicial

            # Formulario rápido y fluido para fijar nombre
            with st.form(key=f"form_nombre_{seleccion_idx}"):
                nombre_input = st.text_input("Nombre para el archivo (sin extensión):", value=st.session_state["nombre_fijado"])
                actualizar = st.form_submit_button("💾 Fijar este nombre")
                if actualizar:
                    st.session_state["nombre_fijado"] = nombre_input

            nombre_final = st.session_state["nombre_fijado"].strip() if st.session_state["nombre_fijado"] else "imagen"
            st.info(f"Nombre activo: **{nombre_final}**")

            # 1. Descarga del archivo ORIGINAL (con su extensión original del PDF)
            nombre_con_extension = f"{nombre_final}.{r['extension']}"
            st.download_button(
                label=f"📥 Descargar Original ({r['extension'].upper()})",
                data=r["bytes"],
                file_name=nombre_con_extension,
                mime=f"image/{r['extension']}",
                use_container_width=True
            )

            # 2. Conversión y descarga a JPEG (Fondo blanco, calidad 100) en memoria al hacer click
            try:
                img_to_convert = Image.open(io.BytesIO(r["bytes"]))
                img_to_convert = ImageOps.exif_transpose(img_to_convert).convert("RGBA")
                fondo = Image.new("RGBA", img_to_convert.size, (255, 255, 255, 255))
                fondo.alpha_composite(img_to_convert)
                
                buffer_jpeg = io.BytesIO()
                fondo.convert("RGB").save(buffer_jpeg, "JPEG", quality=100, optimize=True, progressive=True)
                jpeg_bytes = buffer_jpeg.getvalue()

                st.download_button(
                    label="🖼️ Descargar como JPEG (Fondo blanco, calidad 100)",
                    data=jpeg_bytes,
                    file_name=f"{nombre_final}.jpeg",
                    mime="image/jpeg",
                    use_container_width=True
                )
            except Exception as ex:
                st.error(f"No se pudo preparar la versión JPEG: {ex}")

        st.markdown("---")
        
        # 3. Descargar todas en ZIP (generado directamente en memoria)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, rec in enumerate(image_records, 1):
                zf.writestr(f"imagen_{idx:04d}.{rec['extension']}", rec["bytes"])
        
        st.download_button(
            label="📦 Descargar todas las imágenes originales en un archivo ZIP",
            data=zip_buffer.getvalue(),
            file_name="imagenes_originales_pdf.zip",
            mime="application/zip",
            use_container_width=True
        )
