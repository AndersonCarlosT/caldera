import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Comparador de Perfiles", layout="wide")
st.title("📊 Comparador de Perfiles de Carga + Datos adicionales desde Excel (D3) + Factores de Multiplicación")

col1, col2 = st.columns(2)

with col1:
    st.header("Generación de Dataframes Base")

    meses = {
        "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
        "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
        "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
    }

    mes_seleccionado = st.selectbox("Selecciona el mes", list(meses.keys()))
    numero_mes = meses[mes_seleccionado]

    anio_seleccionado = st.selectbox("Selecciona el año", list(range(2020, 2031)), index=5)

    feriados_input = st.text_input("Días feriados del mes separados por comas (ejemplo: 5,7,15):")

    if feriados_input.strip() != "":
        try:
            dias_feriados = [int(x.strip()) for x in feriados_input.split(",")]
        except:
            st.error("Formato inválido.")
            dias_feriados = []
    else:
        dias_feriados = []

    archivos_lp = st.file_uploader("Sube los archivos .LP", type=["lp"], accept_multiple_files=True)
    archivo_excel = st.file_uploader("Sube el archivo Excel con hojas D3", type=["xlsx"])

    if st.button("Generar Dataframes"):

        # Generar estructura base de fechas desde 00:15
        inicio_mes = datetime(anio_seleccionado, numero_mes, 1, 0, 15)
        if numero_mes == 12:
            fin_mes = datetime(anio_seleccionado + 1, 1, 1)
        else:
            fin_mes = datetime(anio_seleccionado, numero_mes + 1, 1)

        fechas_completas = pd.date_range(start=inicio_mes, end=fin_mes - timedelta(minutes=15), freq="15min")

        df_base = pd.DataFrame({
            "Fecha": fechas_completas.strftime("%d/%m/%Y"),
            "Hora": fechas_completas.strftime("%H:%M:%S")
        })

        # Clasificación HP/HFP
        def clasificar_hp_hfp(fecha_str, hora_str):
            fecha = datetime.strptime(fecha_str + " " + hora_str, "%d/%m/%Y %H:%M:%S")
            dia = fecha.day
            dia_semana = fecha.weekday()

            if dia in dias_feriados or dia_semana == 6:
                return "HFP"

            hora = fecha.time()
            if hora >= datetime.strptime("23:15:00", "%H:%M:%S").time() or hora <= datetime.strptime("18:00:00", "%H:%M:%S").time():
                return "HFP"
            else:
                return "HP"

        df_base["Horario"] = df_base.apply(lambda row: clasificar_hp_hfp(row["Fecha"], row["Hora"]), axis=1)

        # Crear primer dataframe LP
        df_lp = df_base.copy()

        # Factores
        factores = {
            "Acos 1.LP": 100,
            "Acos 2.LP": 100,
            "Nava 1.LP": 1,
            "Nava 2.LP": 200,
            "Ravira 1.LP": 120,
            "Ravira 2.LP": 120
        }

        sumas_por_base = {}
        nombres_lp = []

        for archivo in archivos_lp:
            contenido = archivo.read().decode('utf-8')
            lineas = contenido.splitlines()

            # Buscar encabezado
            indice_inicio = None
            for i, linea in enumerate(lineas):
                if linea.strip().startswith("Fecha/Hora"):
                    indice_inicio = i
                    break

            if indice_inicio is None:
                st.error(f"No se encontró 'Fecha/Hora' en {archivo.name}.")
                continue

            tabla = "\n".join(lineas[indice_inicio:])
            df_temp = pd.read_csv(io.StringIO(tabla), sep=";", engine='python')
            df_temp.columns = [col.strip() for col in df_temp.columns]
            df_temp = df_temp.applymap(lambda x: x.strip() if isinstance(x, str) else x)
            df_temp = df_temp.dropna(axis=1, how='all')

            df_temp['Fecha/Hora'] = pd.to_datetime(df_temp['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')
            df_temp['Fecha'] = df_temp['Fecha/Hora'].dt.strftime("%d/%m/%Y")
            df_temp['Hora'] = df_temp['Fecha/Hora'].dt.strftime("%H:%M:%S")

            col_lp = archivo.name
            nombres_lp.append(col_lp)

            df_merge = df_base.copy()  # Partimos de la base
            df_temp_match = df_temp[['Fecha', 'Hora', '+P/kW']].copy()
            df_merge = pd.merge(df_merge, df_temp_match, on=['Fecha', 'Hora'], how='left')
            df_merge = df_merge.rename(columns={'+P/kW': col_lp})
            df_merge[col_lp] = df_merge[col_lp].astype(float).fillna(0)

            df_lp[col_lp] = df_merge[col_lp]

            # Multiplicación por factor
            factor = factores.get(col_lp, 1)
            nueva_col = f"{col_lp} * Factor"
            df_lp[nueva_col] = df_lp[col_lp] * factor

            # Sumas por nombre base
            nombre_base = re.sub(r'\d+', '', col_lp).replace('.LP', '').strip()
            if nombre_base not in sumas_por_base:
                sumas_por_base[nombre_base] = df_lp[nueva_col].copy()
            else:
                sumas_por_base[nombre_base] += df_lp[nueva_col]

        for nombre_base, suma in sumas_por_base.items():
            df_lp[f"{nombre_base} (Total)"] = suma

        st.subheader("Primer DataFrame: LP con factores y sumas")
        st.dataframe(df_lp, use_container_width=True)

        # Segundo dataframe D3
        df_d3 = df_base.copy()

        if archivo_excel:
            excel_data = pd.ExcelFile(archivo_excel)
            hojas_objetivo = [hoja for hoja in excel_data.sheet_names if hoja.upper() in ["ACOS", "RAVIRA", "NAVA", "CANTA"]]

            for hoja in hojas_objetivo:
                df_hoja = pd.read_excel(archivo_excel, sheet_name=hoja, header=None)

                df_hoja['FechaTmp'] = pd.to_datetime(df_hoja[1], errors='coerce')
                df_hoja['HoraTmp'] = df_hoja[2].astype(str).str.strip()

                df_hoja = df_hoja[df_hoja['FechaTmp'].notna() & df_hoja['HoraTmp'].str.match(r'^\d{2}:\d{2}(:\d{2})?$')]

                df_hoja['Fecha'] = df_hoja['FechaTmp'].dt.strftime('%d/%m/%Y')
                df_hoja['Hora'] = df_hoja['HoraTmp']

                df_hoja_out = df_hoja[['Fecha', 'Hora', 3, 4, 5]].copy()
                df_hoja_out.columns = ['Fecha', 'Hora', f'{hoja} 1 (D3)', f'{hoja} 2 (D3)', f'{hoja} 3 (D3)']

                df_d3 = pd.merge(df_d3, df_hoja_out, on=['Fecha', 'Hora'], how='left')

            d3_cols = [col for col in df_d3.columns if "(D3)" in col]
            df_d3[d3_cols] = df_d3[d3_cols].astype(float).fillna(0)

            for hoja in hojas_objetivo:
                col1 = f"{hoja} 1 (D3)"
                col2 = f"{hoja} 2 (D3)"
                df_d3[f"{hoja} (D3 Total)"] = df_d3[col1] + df_d3[col2]

        st.subheader("Segundo DataFrame: Datos D3")
        st.dataframe(df_d3, use_container_width=True)

with col2:

    archivo_g1 = st.file_uploader("Sube el Excel G1", type=["xlsx"], key="g1")

    if archivo_g1:
        # Leer todo el Excel G1 sin modificar estructura
        df_excel_g1 = pd.read_excel(archivo_g1, sheet_name="G-01 CENTRALES", header=None)

        # Procesamiento base para mostrar tabla G1 normal
        nombre_central = df_excel_g1.loc[14:25, 2]
        tipo_generador = df_excel_g1.loc[14:25, 4]
        numero_generador = df_excel_g1.loc[14:25, 5]
        hp_mwh = df_excel_g1.loc[14:25, 9]
        hfp_mwh = df_excel_g1.loc[14:25, 10]
        total_mwh = df_excel_g1.loc[14:25, 11]
        maxima_demanda = df_excel_g1.loc[14:25, 14]

        df_g1_base = pd.DataFrame({
            "Nombre de la Central": nombre_central,
            "Tipo de Generador": tipo_generador,
            "Numero de Generador": numero_generador,
            "HP (MWh)": hp_mwh,
            "HFP (MWh)": hfp_mwh,
            "Total (MWh)": total_mwh,
            "Máxima Demanda (MW)": maxima_demanda
        })

        # Datos adicionales fijos
        nuevas_centrales = ["Central Termica"] * 4
        nuevos_generadores = ["MODASA MP-515", "CUMMINS ZQ-4288", "COMMINS C900", "COMMINS 925kw"]
        nuevos_codigos = ["G0016", "G01044", "G0653", "G0047"]

        nuevas_hp = [df_excel_g1.loc[48, 9], df_excel_g1.loc[53, 9], df_excel_g1.loc[58, 9], df_excel_g1.loc[63, 9]]
        nuevas_hfp = [df_excel_g1.loc[48, 10], df_excel_g1.loc[53, 10], df_excel_g1.loc[58, 10], df_excel_g1.loc[63, 10]]
        nuevas_total = [df_excel_g1.loc[48, 11], df_excel_g1.loc[53, 11], df_excel_g1.loc[58, 11], df_excel_g1.loc[63, 11]]
        nuevas_maxima = [df_excel_g1.loc[48, 14], df_excel_g1.loc[53, 14], df_excel_g1.loc[58, 14], df_excel_g1.loc[63, 14]]

        df_g1_adicional = pd.DataFrame({
            "Nombre de la Central": nuevas_centrales,
            "Tipo de Generador": nuevos_generadores,
            "Numero de Generador": nuevos_codigos,
            "HP (MWh)": nuevas_hp,
            "HFP (MWh)": nuevas_hfp,
            "Total (MWh)": nuevas_total,
            "Máxima Demanda (MW)": nuevas_maxima
        })

        # Concatenar y limpiar
        df_g1 = pd.concat([df_g1_base, df_g1_adicional], ignore_index=True)

        filas_a_eliminar = [2, 5, 8, 11]
        df_g1 = df_g1.drop(filas_a_eliminar).reset_index(drop=True)
        df_g1 = df_g1.fillna(0)

        st.success("Datos de G1 procesados correctamente")
        st.dataframe(df_g1, use_container_width=True)

        # Si ya existen los otros 2 dataframes, mostrar comparativo
        if st.button("Ver Dataframe Final"):

            # Definimos el comparativo
            nombres = ["ACOS", "RAVIRA", "NAVA", "CANTA"]
            tipos = ["Hidroelectrica", "Termica"]

            filas = []

            for nombre in nombres:
                for tipo in tipos:
                    fila = {
                        "Nombre": nombre,
                        "Central": tipo,
                        "Energia (D3)": "",
                        "Demanda (D3)": "",
                        "Energia (G1)": "",
                        "Demanda (G1)": "",
                        "Energia (LP)": "",
                        "Demanda (LP)": ""
                    }

                    # ---------------- D3 ----------------
                    if tipo == "Hidroelectrica":
                        col_d3_total = f"{nombre.upper()} (D3 Total)"
                    else:
                        col_d3_total = f"{nombre.upper()} 3 (D3)"

                    if col_d3_total in df_d3.columns:
                        suma_d3 = df_d3[col_d3_total].astype(float).sum()
                        max_d3 = df_d3[col_d3_total].astype(float).max()
                        fila["Energia (D3)"] = round(suma_d3 / 4000, 5)
                        fila["Demanda (D3)"] = round(max_d3 / 1000, 5)

                    # ---------------- G1 desde df_excel_g1 ----------------
                    if tipo == "Hidroelectrica":
                        fila_excel = {
                            "ACOS": 16, "RAVIRA": 19, "NAVA": 22, "CANTA": 25
                        }[nombre]
                    else:
                        fila_excel = {
                            "ACOS": 48, "RAVIRA": 53, "NAVA": 58, "CANTA": 63
                        }[nombre]

                    energia_g1 = df_excel_g1.iloc[fila_excel, 11]  # L columna → índice 11
                    demanda_g1 = df_excel_g1.iloc[fila_excel, 14]  # O columna → índice 14

                    fila["Energia (G1)"] = energia_g1
                    fila["Demanda (G1)"] = demanda_g1

                    # ---------------- LP ----------------
                    if tipo == "Hidroelectrica":
                        col_lp_total = f"{nombre.capitalize()} (Total)"
                    else:
                        col_lp_total = None  # Termica no usa LP

                    if col_lp_total and col_lp_total in df_lp.columns:
                        suma_lp = df_lp[col_lp_total].astype(float).sum()
                        max_lp = df_lp[col_lp_total].astype(float).max()
                        fila["Energia (LP)"] = round(suma_lp / 4000, 5)
                        fila["Demanda (LP)"] = round(max_lp / 1000, 5)

                    filas.append(fila)

            df_comparativo = pd.DataFrame(filas)

            st.subheader("📊 Comparación Final de Datos")
            st.dataframe(df_comparativo, use_container_width=True)
