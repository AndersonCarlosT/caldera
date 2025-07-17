import streamlit as st
import pandas as pd
import io
from datetime import datetime
import re

st.title("📊 Comparador de Perfiles de Carga + Datos de Excel (Multihojas)")

archivos_lp = st.file_uploader("Sube uno o más archivos .LP", type=["lp"], accept_multiple_files=True)
archivo_excel = st.file_uploader("Sube el archivo Excel con varias hojas", type=["xlsx"])

if archivos_lp and archivo_excel:
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

    # Cargar Excel multihojas
    xls = pd.ExcelFile(archivo_excel)

    # DataFrame base para unir los archivos
    df_final = None

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

        # Leer tabla
        tabla = "\n".join(lineas[indice_inicio:])
        df = pd.read_csv(io.StringIO(tabla), sep=";", engine='python')

        # Limpiar columnas y espacios
        df.columns = [col.strip() for col in df.columns]
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.dropna(axis=1, how='all')

        # Eliminar columna "+Q/kvar" si existe
        columnas_validas = ["Fecha/Hora", "+P/kW"]
        df = df[[col for col in df.columns if col in columnas_validas]]

        # Convertir a datetime
        df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')

        # Filtrar por mes y año
        df_mes = df[(df['Fecha/Hora'].dt.month == numero_mes) & (df['Fecha/Hora'].dt.year == anio_seleccionado)].copy()

        # Separar fecha y hora
        df_mes['Fecha'] = df_mes['Fecha/Hora'].dt.strftime('%d/%m/%Y')
        df_mes['Hora'] = df_mes['Fecha/Hora'].dt.strftime('%H:%M:%S')
        df_mes['Dia'] = df_mes['Fecha/Hora'].dt.day
        df_mes['Dia_semana'] = df_mes['Fecha/Hora'].dt.dayofweek

        # Clasificación HP / HFP
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

        df_mes['Horario'] = df_mes.apply(clasificar, axis=1)

        # Columna auxiliar para ordenar las horas correctamente
        def hora_orden(hora_str):
            if hora_str == "00:00:00":
                return 99999  # Forzar al final
            else:
                h, m, s = map(int, hora_str.split(":"))
                return h * 60 + m

        df_mes['Orden_Hora'] = df_mes['Hora'].apply(hora_orden)

        # Definir nombre de columna como el nombre real del archivo LP
        nombre_columna_lp = archivo.name
        df_merge = df_mes[['Fecha', 'Hora', 'Horario', 'Orden_Hora', '+P/kW']].copy()
        df_merge = df_merge.rename(columns={'+P/kW': nombre_columna_lp})

        # Buscar hoja correspondiente en el Excel
        base_nombre = re.sub(r'\s*\d+', '', archivo.name.split('.')[0]).strip().upper()
        if base_nombre in xls.sheet_names:
            hoja_df = pd.read_excel(archivo_excel, sheet_name=base_nombre)

            # Filtrar solo filas válidas (las que tienen fecha y hora en columnas B y C)
            hoja_df = hoja_df.dropna(subset=[hoja_df.columns[1], hoja_df.columns[2]])

            hoja_df['Fecha'] = pd.to_datetime(hoja_df.iloc[:, 1]).dt.strftime('%d/%m/%Y')
            hoja_df['Hora'] = pd.to_datetime(hoja_df.iloc[:, 2]).dt.strftime('%H:%M:%S')

            # Extraer columnas D y E
            datos_D = hoja_df.iloc[:, 3]
            datos_E = hoja_df.iloc[:, 4]

            # Crear DataFrame de la hoja para merge
            df_excel = pd.DataFrame({
                'Fecha': hoja_df['Fecha'],
                'Hora': hoja_df['Hora'],
                f"{archivo.name.split('.')[0]} 1 (D3)": datos_D,
                f"{archivo.name.split('.')[0]} 2 (D3)": datos_E
            })

            # Unir al dataframe del LP
            df_merge = pd.merge(df_merge, df_excel, on=['Fecha', 'Hora'], how='left')
        else:
            st.warning(f"No se encontró la hoja '{base_nombre}' en el Excel para el archivo {archivo.name}")

        # Merge acumulativo
        if df_final is None:
            df_final = df_merge
        else:
            df_final = pd.merge(df_final, df_merge, on=['Fecha', 'Hora', 'Horario', 'Orden_Hora'], how='outer')

    # Orden final
    df_final = df_final.sort_values(by=['Fecha', 'Orden_Hora']).reset_index(drop=True)
    df_final = df_final.drop(columns=['Orden_Hora'])

    # Mostrar resultado
    st.success(f"Comparativo de {len(archivos_lp)} archivos .LP con datos de Excel (hojas vinculadas)")
    st.write(f"Días feriados ingresados: {dias_feriados}")
    st.dataframe(df_final)
