import os
import shutil
import zipfile
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageOps

st.set_page_config(page_title="Extractor de Imágenes de PDF", page_icon="🖼️", layout="wide")

st.title("🖼️ Extractor de Imágenes Originales de PDF")
st.markdown("Sube un PDF para extraer sus imágenes, previsualizarlas y descargarlas individualmente, en ZIP o convertirlas a JPG.")

# Subir archivo PDF
archivo_subido = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if archivo_subido is not None:
    nombre_pdf = archivo_subido.name
    ruta_pdf = os.path.join("/tmp", nombre_pdf)
    with open(ruta_pdf, "wb") as f:
        f.write(archivo_subido.getbuffer())

    carpeta_salida = "/tmp/imagenes_extraidas"
    if os.path.exists(carpeta_salida):
        shutil.rmtree(carpeta_salida)
    os.makedirs(carpeta_salida, exist_ok=True)

    with st.spinner("Procesando PDF y extrayendo imágenes..."):
        doc = fitz.open(ruta_pdf)
        image_records, xrefs, errores = [], set(), []
        
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
                        ruta = os.path.join(carpeta_salida, nombre)
                        combinado.save(ruta)
                        ext_final, ancho_final, alto_final = "png", combinado.width, combinado.height
                        del combinado, mascara, pix
                    else:
                        nombre = f"imagen_{len(image_records)+1:04d}.{ext}"
                        ruta = os.path.join(carpeta_salida, nombre)
                        with open(ruta, "wb") as f:
                            f.write(datos["image"])
                        ext_final, ancho_final, alto_final = ext, ancho, alto
                    image_records.append({
                        "pagina": num_pagina, "ruta": ruta, "extension": ext_final,
                        "ancho": ancho_final, "alto": alto_final, "smask": bool(smask)
                    })
                except Exception as e:
                    errores.append((num_pagina, xref, str(e)))
        doc.close()

    if not image_records:
        st.error("No se encontraron imágenes extraíbles en este PDF.")
    else:
        st.success(f"¡Extracción exitosa! Se encontraron {len(image_records)} imágenes únicas.")

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
            st.markdown(f"**Detalles:** Página {r['pagina']} | Resolución: {r['ancho']}×{r['alto']} px | Formato: `{r['extension'].upper()}`")
            try:
                with Image.open(r["ruta"]) as img:
                    st.image(img, caption=f"Página {r['pagina']}", use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo mostrar la vista previa: {e}")

        with col2:
            st.markdown("### Opciones de Descarga Personalizada")
            
            # Campo para nombre personalizado
            nombre_sugerido = f"imagen_pag_{r['pagina']}"
            nombre_personalizado = st.text_input("Nombre para el archivo descargado (sin extensión):", value=nombre_sugerido)
            
            nombre_final = nombre_personalizado.strip() if nombre_personalizado else "imagen"

            # 1. Botón directo para descargar en formato original
            nombre_con_extension = f"{nombre_final}.{r['extension']}"
            with open(r["ruta"], "rb") as file_original:
                st.download_button(
                    label=f"📥 Descargar Original ({r['extension'].upper()})",
                    data=file_original,
                    file_name=nombre_con_extension,
                    mime=f"image/{r['extension']}",
                    use_container_width=True
                )

            # 2. Generar y descargar directamente a JPG (con fondo blanco) de forma optimizada
            destino_jpg = f"/tmp/{nombre_final}.jpg"
            try:
                with Image.open(r["ruta"]) as img:
                    img = ImageOps.exif_transpose(img).convert("RGBA")
                    fondo = Image.new("RGBA", img.size, (255, 255, 255, 255))
                    fondo.alpha_composite(img)
                    fondo.convert("RGB").save(destino_jpg, "JPEG", quality=100, optimize=True, progressive=True)
                
                with open(destino_jpg, "rb") as file_jpg:
                    st.download_button(
                        label="🖼️ Descargar como JPG (Fondo blanco, calidad 100)",
                        data=file_jpg,
                        file_name=f"{nombre_final}.jpg",
                        mime="image/jpeg",
                        use_container_width=True
                    )
            except Exception as ex:
                st.error(f"No se pudo preparar la versión JPG: {ex}")

        st.markdown("---")
        
        # 3. Descargar todas en ZIP
        ruta_zip = "/tmp/todas_las_imagenes.zip"
        with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for rec in image_records:
                zf.write(rec["ruta"], arcname=os.path.basename(rec["ruta"]))
        
        with open(ruta_zip, "rb") as f_zip:
            st.download_button(
                label="📦 Descargar todas las imágenes en un archivo ZIP",
                data=f_zip,
                file_name="imagenes_extraidas_pdf.zip",
                mime="application/zip"
            )
