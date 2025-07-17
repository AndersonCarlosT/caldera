import streamlit as st
import pandas as pd
import io
from functools import reduce
import re

st.title("📊 Comparador de archivos .LP con Excel multi-hoja - Etapa 2")

# Múltiple subida de archivos LP
archivos_lp = st.file_uploader("Sube uno o varios archivos .LP", type=["lp"], accept_multiple_files=True)

# Subir archivo Excel adicional
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

    # Feriados
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
    nombres_lp = []

    for archivo in archivos_lp:
        nombre_lp = archivo.name
        nombres_lp.append(nombre_lp)

        contenido = archivo.read().decode('utf-8')
        lineas = contenido.splitlines()

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

        df.columns = [col.strip() for col in df.columns]
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        if "+Q/kvar" in df.columns:
            df = df.drop(columns=["+Q/kvar"])

        df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')

        df = df[(df['Fecha/Hora'].dt.month == numero_mes) & (df['Fecha/Hora'].dt.year == anio_seleccionado)]

        df['Fecha'] = df['Fecha/Hora'].dt.strftime('%d/%m/%Y')
        df['Hora'] = df['Fecha/Hora'].dt.strftime('%H:%M:%S')
        df['Dia'] = df['Fecha/Hora'].dt.day
        df['Dia_semana'] = df['Fecha/Hora'].dt.dayofweek

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

        df_reducido = df[['Fecha', 'Hora', 'Horario', '+P/kW']].copy()
        df_reducido = df_reducido.rename(columns={'+P/kW': nombre_lp})

        dfs.append(df_reducido)

    # Merge de todos los LPs
    df_final = reduce(lambda left, right: pd.merge(left, right, on=['Fecha', 'Hora', 'Horario'], how='outer'), dfs)
    df_final = df_final.sort_values(by=['Fecha', 'Hora']).reset_index(drop=True)

    # Leer el Excel
    excel = pd.ExcelFile(archivo_excel)

    for nombre_lp in nombres_lp:
        # Limpiar nombre (quitar número y extensión, convertir a mayúsculas)
        nombre_base = re.sub(r'\d+', '', nombre_lp)  # Elimina números
        nombre_base = nombre_base.replace('.LP', '').replace('.lp', '').strip().upper()

        if nombre_base in excel.sheet_names:
            df_excel = pd.read_excel(archivo_excel, sheet_name=nombre_base, header=None)

            # Buscar la fila donde empiecen las fechas (por si hay encabezados de texto)
            fila_inicio = None
            for i, fila in df_excel.iterrows():
                if isinstance(fila[1], pd.Timestamp) or isinstance(fila[1], str):
                    try:
                        pd.to_datetime(str(fila[1]), format='%d/%m/%Y')
                        fila_inicio = i
                        break
                    except:
                        continue

            if fila_inicio is None:
                st.warning(f"No se encontró data en la hoja {nombre_base}")
                continue

            df_data = df_excel.iloc[fila_inicio:].copy()
            df_data.columns = ['Index', 'Fecha', 'Hora', 'Col_D', 'Col_E']
            df_data['Fecha'] = pd.to_datetime(df_data['Fecha']).dt.strftime('%d/%m/%Y')
            df_data['Hora'] = df_data['Hora'].astype(str).str.strip()

            # Hacer merge con df_final
            df_merge = df_final.merge(df_data[['Fecha', 'Hora', 'Col_D', 'Col_E']], on=['Fecha', 'Hora'], how='left')

            # Agregar las columnas con nombres correspondientes
            df_final[f"{nombre_lp} (D3)"] = df_merge['Col_D']
            df_final[f"{nombre_lp} (E3)"] = df_merge['Col_E']

        else:
            st.warning(f"No se encontró la hoja '{nombre_base}' en el Excel.")

    st.success("Proceso completado con datos del Excel agregados.")
    st.dataframe(df_final)
