import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Comparador de Perfiles", layout="wide")
st.title("📊 Comparador de Perfiles de Carga + Datos adicionales desde Excel (D3) + Factores de Multiplicación")

col1, col2 = st.columns(2)

with col1:
    st.header("Procesamiento de Perfiles LP y Datos D3")

    archivos_lp = st.file_uploader("Sube uno o más archivos .LP", type=["lp"], accept_multiple_files=True)
    archivo_excel = st.file_uploader("Sube el archivo Excel con múltiples hojas (D3)", type=["xlsx"])

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

    if feriados_input.strip() != "":
        try:
            dias_feriados = [int(x.strip()) for x in feriados_input.split(",")]
        except:
            st.error("Formato inválido. Escriba números separados por comas.")
            dias_feriados = []
    else:
        dias_feriados = []

    if st.button("Generar Dataframes"):

        # 1️⃣ Generar Dataframe base de fechas y horas en bloques de 15min
        inicio_mes = datetime(anio_seleccionado, numero_mes, 1)
        if numero_mes == 12:
            fin_mes = datetime(anio_seleccionado + 1, 1, 1)
        else:
            fin_mes = datetime(anio_seleccionado, numero_mes + 1, 1)

        fechas_completas = pd.date_range(start=inicio_mes, end=fin_mes - pd.Timedelta(minutes=15), freq="15min")

        df_base = pd.DataFrame({
            "Fecha": fechas_completas.strftime('%d/%m/%Y'),
            "Hora": fechas_completas.strftime('%H:%M:%S'),
            "Dia": fechas_completas.day,
            "Dia_semana": fechas_completas.dayofweek
        })

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

        df_base['Horario'] = df_base.apply(clasificar, axis=1)
        df_base = df_base.drop(columns=["Dia", "Dia_semana"])

        df_lp = df_base.copy()  # Este será el primer dataframe

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

        # 2️⃣ Leer cada archivo LP y hacer merge por separado, rellenando con ceros
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

            nombre_columna = archivo.name
            nombres_lp.append(nombre_columna)

            df_merge = pd.merge(df_base[['Fecha', 'Hora']], df_mes[['Fecha', 'Hora', '+P/kW']],
                                on=['Fecha', 'Hora'], how='left')
            df_lp[nombre_columna] = df_merge['+P/kW'].fillna(0)

        # 3️⃣ Multiplicar por factores y sumar por nombre base
        for nombre_lp in nombres_lp:
            factor = factores.get(nombre_lp, 1)
            nueva_col = f"{nombre_lp} * Factor"
            df_lp[nueva_col] = df_lp[nombre_lp].astype(float) * factor

        sumas_por_base = {}

        for nombre_lp in nombres_lp:
            nombre_base = re.sub(r'\d+', '', nombre_lp).replace('.LP', '').strip()
            columna_factor = f"{nombre_lp} * Factor"

            if nombre_base not in sumas_por_base:
                sumas_por_base[nombre_base] = df_lp[columna_factor].copy()
            else:
                sumas_por_base[nombre_base] += df_lp[columna_factor]

        for nombre_base, suma in sumas_por_base.items():
            df_lp[f"{nombre_base} (Total)"] = suma

        st.subheader("Primer DataFrame: Datos LP con Huecos Rellenados y Factores")
        st.dataframe(df_lp)

        # 4️⃣ Procesar Excel D3 (Segundo dataframe)
        if archivo_excel:
            excel_data = pd.ExcelFile(archivo_excel)
            df_d3 = df_base.copy()

            for nombre_hoja in ["ACOS", "RAVIRA", "NAVA", "CANTA"]:
                if nombre_hoja in excel_data.sheet_names:
                    df_hoja = pd.read_excel(archivo_excel, sheet_name=nombre_hoja, header=None)

                    df_hoja['FechaTmp'] = pd.to_datetime(df_hoja[1], errors='coerce')
                    df_hoja['HoraTmp'] = df_hoja[2].astype(str).str.strip()
                    df_hoja = df_hoja[df_hoja['FechaTmp'].notna() & df_hoja['HoraTmp'].str.match(r'^\d{2}:\d{2}(:\d{2})?$')]

                    df_hoja['Fecha'] = df_hoja['FechaTmp'].dt.strftime('%d/%m/%Y')
                    df_hoja['Hora'] = df_hoja['HoraTmp']

                    df_merge = pd.merge(df_base[['Fecha', 'Hora']], df_hoja[['Fecha', 'Hora', 3, 4, 5]],
                                        on=['Fecha', 'Hora'], how='left')

                    df_d3[f"{nombre_hoja} 1 (D3)"] = df_merge[3].fillna(0)
                    df_d3[f"{nombre_hoja} 2 (D3)"] = df_merge[4].fillna(0)
                    df_d3[f"{nombre_hoja} 3 (D3)"] = df_merge[5].fillna(0)

                    df_d3[f"{nombre_hoja} (D3 Total)"] = df_d3[[f"{nombre_hoja} 1 (D3)", f"{nombre_hoja} 2 (D3)"]].sum(axis=1)

                else:
                    st.warning(f"No se encontró la hoja '{nombre_hoja}' en el Excel.")

            st.subheader("Segundo DataFrame: Datos D3 con Huecos Rellenados")
            st.dataframe(df_d3)

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
