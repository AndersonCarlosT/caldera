import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Comparador de Perfiles", layout="wide")
st.title("📊 Comparador de Perfiles de Carga + Datos adicionales desde Excel (D3) + Factores de Multiplicación")

col1, col2 = st.columns(2)


with col1:
    archivos_lp = st.file_uploader("Sube uno o más archivos .LP", type=["lp"], accept_multiple_files=True)
    archivo_excel = st.file_uploader("Sube el archivo Excel con múltiples hojas", type=["xlsx"])

    # Selector de mes y año
    meses = {
        "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
        "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
        "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
    }

    mes_seleccionado = st.selectbox("Selecciona el mes", list(meses.keys()))
    numero_mes = meses[mes_seleccionado]
    anio_seleccionado = st.selectbox("Selecciona el año", list(range(2020, 2031)), index=5)

    feriados_input = st.text_input(f"Ingrese los días feriados de {mes_seleccionado} separados por comas (ejemplo: 5,7,15):")

    dias_feriados = []
    if feriados_input.strip() != "":
        try:
            dias_feriados = [int(x.strip()) for x in feriados_input.split(",")]
        except:
            st.error("Formato inválido. Escriba números separados por comas.")

    if st.button("Generar Dataframes") and archivos_lp and archivo_excel:

        # 1️⃣ Generar dataframe base de fechas y horas
        inicio_mes = datetime(anio_seleccionado, numero_mes, 1)
        if numero_mes == 12:
            fin_mes = datetime(anio_seleccionado + 1, 1, 1)
        else:
            fin_mes = datetime(anio_seleccionado, numero_mes + 1, 1)

        fechas_completas = pd.date_range(start=inicio_mes, end=fin_mes - timedelta(minutes=15), freq="15min")

        df_base = pd.DataFrame({'Fecha/Hora': fechas_completas})
        df_base['Fecha'] = df_base['Fecha/Hora'].dt.strftime('%d/%m/%Y')
        df_base['Hora'] = df_base['Fecha/Hora'].dt.strftime('%H:%M:%S')
        df_base['Dia'] = df_base['Fecha/Hora'].dt.day
        df_base['Dia_semana'] = df_base['Fecha/Hora'].dt.dayofweek

        def clasificar(row):
            dia = row['Dia']
            dia_semana = row['Dia_semana']
            hora = pd.to_datetime(row['Hora'], format='%H:%M:%S').time()

            if dia in dias_feriados or dia_semana == 6:
                return "HFP"
            if hora >= pd.to_datetime("23:15:00", format='%H:%M:%S').time() or hora <= pd.to_datetime("18:00:00", format='%H:%M:%S').time():
                return "HFP"
            return "HP"

        df_base['Horario'] = df_base.apply(clasificar, axis=1)

        df_lp = df_base[['Fecha', 'Hora', 'Horario']].copy()

        # 2️⃣ Leer archivos .LP y hacer match con df_lp
        factores = {
            "Acos 1.LP": 100,
            "Acos 2.LP": 100,
            "Nava 1.LP": 1,
            "Nava 2.LP": 200,
            "Ravira 1.LP": 120,
            "Ravira 2.LP": 120,
            "Canta 1.LP": 1,
            "Canta 2.LP": 1
        }

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
                st.error(f"No se encontró la cabecera 'Fecha/Hora' en {archivo.name}.")
                continue

            tabla = "\n".join(lineas[indice_inicio:])
            df = pd.read_csv(io.StringIO(tabla), sep=";", engine='python')

            df.columns = [col.strip() for col in df.columns]
            df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

            df = df[['Fecha/Hora', '+P/kW']]
            df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')
            df['Fecha'] = df['Fecha/Hora'].dt.strftime('%d/%m/%Y')
            df['Hora'] = df['Fecha/Hora'].dt.strftime('%H:%M:%S')

            nombre_columna = archivo.name
            nombres_lp.append(nombre_columna)

            df_lp = pd.merge(df_lp, df[['Fecha', 'Hora', '+P/kW']], on=['Fecha', 'Hora'], how='left')
            df_lp = df_lp.rename(columns={'+P/kW': nombre_columna})

            df_lp[nombre_columna] = df_lp[nombre_columna].fillna(0)

        # 3️⃣ Agregar columnas de multiplicación y suma por base
        sumas_por_base = {}

        for nombre_lp in nombres_lp:
            factor = factores.get(nombre_lp, 1)
            columna_factor = f"{nombre_lp} * Factor"
            df_lp[columna_factor] = df_lp[nombre_lp].astype(float) * factor

            nombre_base = re.sub(r'\d+', '', nombre_lp).replace('.LP', '').strip()

            if nombre_base not in sumas_por_base:
                sumas_por_base[nombre_base] = df_lp[columna_factor].copy()
            else:
                sumas_por_base[nombre_base] += df_lp[columna_factor]

        for nombre_base, suma in sumas_por_base.items():
            df_lp[f"{nombre_base} (Total)"] = suma

        st.subheader("Primer dataframe - Datos LP")
        st.dataframe(df_lp, use_container_width=True)

        # 4️⃣ Segundo dataframe - D3
        hojas_objetivo = ["ACOS", "RAVIRA", "NAVA", "CANTA"]
        excel_data = pd.ExcelFile(archivo_excel)

        df_d3 = df_base[['Fecha', 'Hora', 'Horario']].copy()

        for hoja in hojas_objetivo:
            if hoja in excel_data.sheet_names:
                df_hoja = pd.read_excel(archivo_excel, sheet_name=hoja, header=None)
                df_hoja['Fecha'] = pd.to_datetime(df_hoja[1], errors='coerce').dt.strftime('%d/%m/%Y')
                df_hoja['Hora'] = df_hoja[2].astype(str).str.strip()

                df_hoja = df_hoja[df_hoja['Fecha'].notna() & df_hoja['Hora'].str.match(r'^\d{2}:\d{2}(:\d{2})?$')]

                d_col = f"{hoja} 1 (D3)"
                e_col = f"{hoja} 2 (D3)"
                f_col = f"{hoja} 3 (D3)"

                df_temp = df_hoja[['Fecha', 'Hora', 3, 4, 5]].copy()
                df_temp = df_temp.rename(columns={3: d_col, 4: e_col, 5: f_col})

                df_d3 = pd.merge(df_d3, df_temp, on=['Fecha', 'Hora'], how='left')

                # Sumar columnas D y E
                df_d3[f"{hoja} (D3 Total)"] = df_d3[[d_col, e_col]].astype(float).sum(axis=1)
            else:
                st.warning(f"No se encontró la hoja {hoja} en el Excel.")

        st.subheader("Segundo dataframe - Datos D3")
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
