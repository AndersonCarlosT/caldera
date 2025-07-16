import streamlit as st
import pandas as pd
import io

st.title("📊 Lector de archivos .LP - Filtro por Mes")

archivo_lp = st.file_uploader("Sube tu archivo .LP", type=["lp"])

if archivo_lp is not None:
    # Leer el archivo
    contenido = archivo_lp.read().decode('utf-8')
    lineas = contenido.splitlines()

    # Buscar el inicio de la tabla
    indice_inicio = None
    for i, linea in enumerate(lineas):
        if linea.strip().startswith("Fecha/Hora"):
            indice_inicio = i
            break

    if indice_inicio is None:
        st.error("No se encontró la cabecera 'Fecha/Hora' en el archivo.")
    else:
        # Leer la tabla
        tabla = "\n".join(lineas[indice_inicio:])
        df = pd.read_csv(io.StringIO(tabla), sep=";", engine='python')

        # Limpiar columnas y espacios
        df.columns = [col.strip() for col in df.columns]
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.dropna(axis=1, how='all')

        # Convertir a datetime
        df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')

        # Selector de mes
        meses = {
            "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
            "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
            "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
        }

        mes_seleccionado = st.selectbox("Selecciona el mes a filtrar", list(meses.keys()))

        # Filtrar por mes
        numero_mes = meses[mes_seleccionado]
        df_filtrado = df[df['Fecha/Hora'].dt.month == numero_mes]

        # Mostrar el DataFrame filtrado
        st.success(f"Mostrando datos del mes de {mes_seleccionado}")
        st.dataframe(df_filtrado)
