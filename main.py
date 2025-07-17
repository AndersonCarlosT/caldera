import streamlit as st
import pandas as pd
import io
from datetime import datetime
from functools import reduce

st.title("📊 Segunda Etapa - Cruce con Excel adicional")

# Asumimos que ya tienes el df_final de la etapa anterior
# Para este ejemplo, vamos a pedir que lo cargues de nuevo aquí por simplicidad

st.subheader("⚙️ Suba el DataFrame consolidado de los archivos LP (CSV temporal)")

archivo_consolidado = st.file_uploader("Sube el archivo CSV consolidado de los LP", type=["csv"])

if archivo_consolidado is not None:
    df_final = pd.read_csv(archivo_consolidado)

    # Subir el Excel adicional
    st.subheader("📂 Suba el archivo Excel con múltiples hojas")
    excel_file = st.file_uploader("Sube el Excel", type=["xlsx"])

    if excel_file is not None:
        xls = pd.ExcelFile(excel_file)

        # Identificar columnas LP en el dataframe consolidado
        columnas_lp = [col for col in df_final.columns if col.endswith(".LP")]

        for col_lp in columnas_lp:
            nombre_base = col_lp.split()[0].upper()  # Ej: "ACOS" de "Acos 1.LP"

            # Verificar si hay una hoja con ese nombre
            if nombre_base in xls.sheet_names:
                df_excel = pd.read_excel(excel_file, sheet_name=nombre_base, header=None)

                # Buscar dónde empiezan las filas válidas (asumimos que hay texto arriba)
                # Buscamos filas donde la columna B tenga un valor tipo fecha
                inicio_datos = None
                for i, val in enumerate(df_excel[1]):
                    try:
                        pd.to_datetime(val)
                        inicio_datos = i
                        break
                    except:
                        continue

                if inicio_datos is None:
                    st.warning(f"No se encontraron datos con fechas en la hoja {nombre_base}")
                    continue

                # Leer solo los datos válidos
                df_match = df_excel.iloc[inicio_datos:].copy()
                df_match.columns = ['ColA', 'Fecha', 'Hora', 'D', 'E']

                # Convertir fechas y horas a string para hacer el match
                df_match['Fecha'] = pd.to_datetime(df_match['Fecha']).dt.strftime('%d/%m/%Y')
                df_match['Hora'] = pd.to_datetime(df_match['Hora']).dt.strftime('%H:%M:%S')

                # Hacer merge con el dataframe final
                df_temp = df_final[['Fecha', 'Hora']].copy()
                df_temp = df_temp.merge(df_match[['Fecha', 'Hora', 'D', 'E']], on=['Fecha', 'Hora'], how='left')

                # Crear nuevos nombres de columnas
                df_final[f"{col_lp.split('.')[0]} 1 (D3)"] = df_temp['D']
                df_final[f"{col_lp.split('.')[0]} 2 (D3)"] = df_temp['E']

            else:
                st.warning(f"No se encontró la hoja '{nombre_base}' en el Excel. Se omitirá '{col_lp}'.")

        st.success("Cruce completado con éxito")
        st.dataframe(df_final)
