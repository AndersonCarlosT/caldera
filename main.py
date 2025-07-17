import streamlit as st
import pandas as pd
import io
from datetime import datetime

st.title("📊 Comparador de archivos .LP - Filtro por Mes, Feriados y HP/HFP")

archivos_lp = st.file_uploader("Sube uno o más archivos .LP", type=["lp"], accept_multiple_files=True)

if archivos_lp:
    # Selector de mes y año
    meses = {
        "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
        "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
        "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
    }

    col1, col2 = st.columns(2)
    with col1:
        mes_seleccionado = st.selectbox("Selecciona el mes", list(meses.keys()))
        numero_mes = meses[mes_seleccionado]

    with col2:
        anio_seleccionado = st.selectbox("Selecciona el año", list(range(2020, 2031)), index=5)  # Default 2025

    # Input de feriados
    feriados_input = st.text_input(f"Ingrese los días feriados de {mes_seleccionado} separados por comas (ejemplo: 5,7,15):")

    if feriados_input.strip() != "":
        try:
            dias_feriados = [int(x.strip()) for x in feriados_input.split(",")]
        except:
            st.error("Formato inválido. Escriba números separados por comas.")
            dias_feriados = []
    else:
        dias_feriados = []

    # Procesar cada archivo
    dataframes = []

    for archivo in archivos_lp:
        nombre_archivo = archivo.name.replace(".lp", "")

        contenido = archivo.read().decode('utf-8')
        lineas = contenido.splitlines()

        # Buscar inicio de tabla
        indice_inicio = None
        for i, linea in enumerate(lineas):
            if linea.strip().startswith("Fecha/Hora"):
                indice_inicio = i
                break

        if indice_inicio is None:
            st.error(f"No se encontró la cabecera 'Fecha/Hora' en el archivo {archivo.name}.")
            continue

        tabla = "\n".join(lineas[indice_inicio:])
        df = pd.read_csv(io.StringIO(tabla), sep=";", engine='python')

        # Limpiar columnas y espacios
        df.columns = [col.strip() for col in df.columns]
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.dropna(axis=1, how='all')

        # Eliminar "+Q/kvar"
        if "+Q/kvar" in df.columns:
            df = df.drop(columns=["+Q/kvar"])

        # Convertir a datetime
        df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')

        # Filtrar por mes y año
        df = df[(df['Fecha/Hora'].dt.month == numero_mes) & (df['Fecha/Hora'].dt.year == anio_seleccionado)]

        # Separar fecha y hora
        df['Fecha'] = df['Fecha/Hora'].dt.strftime('%d/%m/%Y')
        df['Hora'] = df['Fecha/Hora'].dt.strftime('%H:%M:%S')
        df['Dia'] = df['Fecha/Hora'].dt.day
        df['Dia_semana'] = df['Fecha/Hora'].dt.dayofweek

        # Mantener solo la columna "+P/kW" y renombrarla con el nombre del archivo
        df = df[['Fecha', 'Hora', 'Dia', 'Dia_semana', '+P/kW']]
        df = df.rename(columns={"+P/kW": nombre_archivo})

        dataframes.append(df)

    if len(dataframes) == 0:
        st.stop()

    # Hacer merge de todos los dataframes por Fecha y Hora
    df_final = dataframes[0][['Fecha', 'Hora', 'Dia', 'Dia_semana', list(dataframes[0].columns)[4]]].copy()

    for df in dataframes[1:]:
        df_final = pd.merge(df_final, df[['Fecha', 'Hora', list(df.columns)[4]]], on=['Fecha', 'Hora'], how='outer')

    # Clasificación HP / HFP con feriados y domingos
    def clasificar(row):
        dia = row['Dia']
        dia_semana = row['Dia_semana']
        hora = pd.to_datetime(row['Hora'], format='%H:%M:%S').time()

        if dia in dias_feriados or dia_semana == 6:
            return "HFP"
        if hora >= pd.to_datetime("23:15:00", format='%H:%M:%S').time() or hora <= pd.to_datetime("18:00:00", format='%H:%M:%S').time():
            return "HFP"
        else:
            return "HP"

    df_final['Horario'] = df_final.apply(clasificar, axis=1)

    # Ordenar columnas
    columnas_resultado = ['Fecha', 'Hora', 'Horario'] + [col for col in df_final.columns if col not in ['Fecha', 'Hora', 'Dia', 'Dia_semana', 'Horario']]
    df_final = df_final[columnas_resultado]

    # Mostrar resultado
    st.success("Comparación completada:")
    st.write(f"Días feriados ingresados: {dias_feriados}")
    st.dataframe(df_final)
