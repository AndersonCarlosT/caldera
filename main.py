import streamlit as st
import pandas as pd
import io
from datetime import datetime
import re

st.title("📊 Comparador de Perfiles de Carga + Datos adicionales desde Excel (D3)")

archivos_lp = st.file_uploader("Sube uno o más archivos .LP", type=["lp"], accept_multiple_files=True)

archivo_excel = st.file_uploader("Sube el archivo Excel con múltiples hojas", type=["xlsx"])

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

    feriados_input = st.text_input(f"Ingrese los días feriados de {mes_seleccionado} separados por comas (ejemplo: 5,7,15):")

    if feriados_input.strip() != "":
        try:
            dias_feriados = [int(x.strip()) for x in feriados_input.split(",")]
        except:
            st.error("Formato inválido. Escriba números separados por comas.")
            dias_feriados = []
    else:
        dias_feriados = []

    df_final = None
    nombres_lp = []

    for archivo in archivos_lp:
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
        df = df.dropna(axis=1, how='all')

        columnas_validas = ["Fecha/Hora", "+P/kW"]
        df = df[[col for col in df.columns if col in columnas_validas]]

        df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')

        df_mes = df[(df['Fecha/Hora'].dt.month == numero_mes) & (df['Fecha/Hora'].dt.year == anio_seleccionado)].copy()

        df_mes['Fecha'] = df_mes['Fecha/Hora'].dt.strftime('%d/%m/%Y')
        df_mes['Hora'] = df_mes['Fecha/Hora'].dt.strftime('%H:%M:%S')
        df_mes['Dia'] = df_mes['Fecha/Hora'].dt.day
        df_mes['Dia_semana'] = df_mes['Fecha/Hora'].dt.dayofweek

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

        def hora_orden(hora_str):
            if hora_str == "00:00:00":
                return 99999
            else:
                h, m, s = map(int, hora_str.split(":"))
                return h * 60 + m

        df_mes['Orden_Hora'] = df_mes['Hora'].apply(hora_orden)

        nombre_columna = archivo.name
        nombres_lp.append(nombre_columna)

        df_merge = df_mes[['Fecha', 'Hora', 'Horario', 'Orden_Hora', '+P/kW']].copy()
        df_merge = df_merge.rename(columns={'+P/kW': nombre_columna})

        if df_final is None:
            df_final = df_merge
        else:
            df_final = pd.merge(df_final, df_merge, on=['Fecha', 'Hora', 'Horario', 'Orden_Hora'], how='outer')

    df_final = df_final.sort_values(by=['Fecha', 'Orden_Hora']).reset_index(drop=True)
    df_final = df_final.drop(columns=['Orden_Hora'])

    # Cargar el Excel con múltiples hojas
    excel_data = pd.ExcelFile(archivo_excel)

    # Controlar qué hojas ya se procesaron
    hojas_procesadas = set()

    for nombre_lp in nombres_lp:
        nombre_base = re.sub(r'\d+', '', nombre_lp)  
        nombre_base = nombre_base.replace('.LP', '').strip().upper()

        if nombre_base in excel_data.sheet_names:

            if nombre_base not in hojas_procesadas:
                hojas_procesadas.add(nombre_base)

                df_hoja = pd.read_excel(archivo_excel, sheet_name=nombre_base, header=None)

                # Convertir columna B a fecha
                df_hoja['FechaTmp'] = pd.to_datetime(df_hoja[1], errors='coerce')

                # Convertir columna C a texto de hora
                df_hoja['HoraTmp'] = df_hoja[2].astype(str).str.strip()

                # Filtrar filas válidas
                df_hoja = df_hoja[df_hoja['FechaTmp'].notna() & df_hoja['HoraTmp'].str.match(r'^\d{2}:\d{2}(:\d{2})?$')]

                # Formatear columnas
                df_hoja['Fecha'] = df_hoja['FechaTmp'].dt.strftime('%d/%m/%Y')
                df_hoja['Hora'] = df_hoja['HoraTmp']

                df_hoja = df_hoja.drop(columns=['FechaTmp', 'HoraTmp'])

                # Crear nombres de columnas D, E y F usando nombre de hoja
                nombre_d = f"{nombre_base} 1 (D3)"
                nombre_e = f"{nombre_base} 2 (D3)"
                nombre_f = f"{nombre_base} 3 (D3)"

                df_hoja_out = df_hoja[['Fecha', 'Hora', 3, 4, 5]].copy()
                df_hoja_out = df_hoja_out.rename(columns={3: nombre_d, 4: nombre_e, 5: nombre_f})

                # Merge al dataframe final
                df_final = pd.merge(df_final, df_hoja_out, on=['Fecha', 'Hora'], how='left')

        else:
            st.warning(f"No se encontró la hoja '{nombre_base}' en el Excel.")

    # Reordenar columnas para poner D3 al lado del archivo LP correspondiente
    cols = df_final.columns.tolist()

    for nombre_lp in nombres_lp:
        nombre_base = re.sub(r'\d+', '', nombre_lp)  
        nombre_base = nombre_base.replace('.LP', '').strip().upper()

        nombre_d = f"{nombre_base} 1 (D3)"
        nombre_e = f"{nombre_base} 2 (D3)"
        nombre_f = f"{nombre_base} 3 (D3)"

        if nombre_d in cols and nombre_e in cols and nombre_f in cols:
            idx_lp = cols.index(nombre_lp)

            # Quitar D3 de su posición actual
            cols.remove(nombre_d)
            cols.remove(nombre_e)
            cols.remove(nombre_f)

            # Insertar D3 al lado del LP
            cols = cols[:idx_lp + 1] + [nombre_d, nombre_e, nombre_f] + cols[idx_lp + 1:]

    df_final = df_final[cols]

    st.success("Proceso completado. Se añadieron columnas D3 al dataframe.")
    st.dataframe(df_final)
