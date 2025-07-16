import streamlit as st
import pandas as pd
import io

st.title("📊 Lector de archivos .LP - Perfil de Carga")

archivo_lp = st.file_uploader("Sube tu archivo .LP", type=["lp"])

if archivo_lp is not None:
    # Leemos el archivo como texto
    contenido = archivo_lp.read().decode('utf-8')
    
    # Convertimos a lista de líneas
    lineas = contenido.splitlines()

    # Filtramos solo las líneas que contienen la tabla
    # Esto depende de tu formato, pero normalmente empieza en "Fecha/Hora"
    indice_inicio = None
    for i, linea in enumerate(lineas):
        if linea.strip().startswith("Fecha/Hora"):
            indice_inicio = i
            break

    if indice_inicio is None:
        st.error("No se encontró la cabecera 'Fecha/Hora' en el archivo.")
    else:
        # Tomamos desde la cabecera hacia abajo
        tabla = "\n".join(lineas[indice_inicio:])

        # Leemos la tabla con pandas usando ; como separador
        df = pd.read_csv(io.StringIO(tabla), sep=";", engine='python')

        # Limpiamos espacios y columnas vacías
        df.columns = [col.strip() for col in df.columns]
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.dropna(axis=1, how='all')  # Elimina columnas vacías

        # Mostramos el DataFrame en Streamlit
        st.success("Archivo leído correctamente ✅")
        st.dataframe(df)

        # Opcional: descargar como Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Perfil de Carga')
        st.download_button(
            label="Descargar Excel",
            data=output.getvalue(),
            file_name="perfil_carga.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
