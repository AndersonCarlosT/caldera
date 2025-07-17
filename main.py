import streamlit as st
import pandas as pd
import io

st.title("📊 Comparador de múltiples archivos .LP - Consolidación de +P/kW")

# Múltiple subida de archivos
archivos_lp = st.file_uploader("Sube uno o varios archivos .LP", type=["lp"], accept_multiple_files=True)

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
        anio_seleccionado = st.selectbox("Selecciona el año", list(range(2020, 2031)), index=5)

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

    dfs = []
    for archivo in archivos_lp:
        contenido = archivo.read().decode('utf-8')
        lineas = contenido.splitlines()

        # Buscar inicio de la tabla
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

        # Eliminar la columna "+Q/kvar"
        if "+Q/kvar" in df.columns:
            df = df.drop(columns=["+Q/kvar"])

        # Convertir Fecha/Hora
        df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')

        # Filtrar por mes y año
        df = df[(df['Fecha/Hora'].dt.month == numero_mes) & (df['Fecha/Hora'].dt.year == anio_seleccionado)]

        # Separar Fecha y Hora
        df['Fecha'] = df['Fecha/Hora'].dt.strftime('%d/%m/%Y')
        df['Hora'] = df['Fecha/Hora'].dt.strftime('%H:%M:%S')
        df['Dia'] = df['Fecha/Hora'].dt.day
        df['Dia_semana'] = df['Fecha/Hora'].dt.dayofweek

        # Clasificar HP / HFP
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

        df['Horario'] = df.apply(clasificar, axis=1)

        # Crear dataframe reducido con nombre de archivo como columna
        nombre_archivo = archivo.name.split('.')[0]
        df_reducido = df[['Fecha', 'Hora', 'Horario', '+P/kW']].copy()
        df_reducido = df_reducido.rename(columns={'+P/kW': nombre_archivo})

        dfs.append(df_reducido)

    # Unir todos los archivos por Fecha y Hora
    from functools import reduce

    df_final = reduce(lambda left, right: pd.merge(left, right, on=['Fecha', 'Hora', 'Horario'], how='outer'), dfs)

    # Ordenar por Fecha y Hora
    df_final = df_final.sort_values(by=['Fecha', 'Hora']).reset_index(drop=True)

    st.success("Consolidación completada")
    st.dataframe(df_final)
