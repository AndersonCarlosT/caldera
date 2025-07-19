import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Comparador de Perfiles", layout="wide")
st.title("📊 Comparador de Perfiles de Carga + Datos adicionales desde Excel (D3) + Factores de Multiplicación")

col1, col2 = st.columns(2)

with col1:
    st.title("🔌 Visualizador de Perfil de Carga (.LP) con Intervalos de 15 Minutos")
    
    # Selección de año y mes
    anio = st.selectbox("Selecciona el Año", list(range(2020, datetime.now().year + 1)), index=datetime.now().year - 2020)
    mes = st.selectbox("Selecciona el Mes", list(range(1, 13)), index=datetime.now().month - 1)
    
    # Función para generar el dataframe base
    def generar_base(anio, mes):
        inicio = datetime(anio, mes, 1)
        if mes == 12:
            fin = datetime(anio + 1, 1, 1)
        else:
            fin = datetime(anio, mes + 1, 1)
    
        fechas = []
        horas = []
    
        fecha_actual = inicio
        while fecha_actual < fin:
            for i in range(96):  # 96 intervalos de 15 minutos
                if i < 95:
                    hora_intervalo = (datetime.min + timedelta(minutes=15*(i+1))).time()
                else:
                    hora_intervalo = datetime.min.time()  # 00:00 al final del día
                fechas.append(fecha_actual.strftime("%d/%m/%Y"))
                horas.append(hora_intervalo.strftime("%H:%M"))
            fecha_actual += timedelta(days=1)
    
        df_base = pd.DataFrame({
            "Fecha": fechas,
            "Hora": horas
        })
        return df_base
    
    df_base = generar_base(anio, mes)
    
    st.write("### DataFrame Base Generado:")
    st.dataframe(df_base)
    
    # Función para leer archivo .LP
    def leer_archivo_lp(archivo):
        contenido = archivo.read().decode("utf-8").splitlines()
    
        # Buscar línea donde empiezan los datos
        for i, linea in enumerate(contenido):
            if linea.strip().startswith("Fecha/Hora"):
                inicio_datos = i + 1
                break
    
        # Leer los datos desde la línea identificada
        datos = "\n".join(contenido[inicio_datos:])
    
        df_lp = pd.read_csv(io.StringIO(datos), sep=";", engine="python", skipinitialspace=True)
    
        # Limpiar columnas
        df_lp.columns = [col.strip() for col in df_lp.columns]
    
        # Extraer solo Fecha/Hora y +P/kW
        df_lp = df_lp[["Fecha/Hora", "+P/kW"]]
    
        # Separar fecha y hora en formato requerido
        df_lp["Fecha"] = pd.to_datetime(df_lp["Fecha/Hora"], dayfirst=True).dt.strftime("%d/%m/%Y")
        df_lp["Hora"] = pd.to_datetime(df_lp["Fecha/Hora"], dayfirst=True).dt.strftime("%H:%M")
    
        # Renombrar columna de datos
        df_lp.rename(columns={"+P/kW": "Dato"}, inplace=True)
    
        # Dejar solo las columnas necesarias
        df_lp = df_lp[["Fecha", "Hora", "Dato"]]
    
        return df_lp
    
    # Subir archivo LP
    archivo_lp = st.file_uploader("📂 Sube el archivo LP (.LP)", type=["LP", "lp"])
    
    if archivo_lp is not None:
        df_lp = leer_archivo_lp(archivo_lp)
    
        st.write("### Datos extraídos del archivo LP:")
        st.dataframe(df_lp)
    
        # Hacer merge con el dataframe base
        df_resultado = pd.merge(df_base, df_lp, on=["Fecha", "Hora"], how="left")
    
        # Rellenar valores faltantes con 0
        df_resultado["Dato"] = df_resultado["Dato"].fillna(0)
    
        st.write("### DataFrame Final con Match:")
        st.dataframe(df_resultado)
    
        # Descargar resultado en CSV
        output = io.StringIO()
        df_resultado.to_csv(output, index=False, sep=";", decimal=".", encoding="utf-8")
        output.seek(0)
    
        st.download_button(
            label="📥 Descargar CSV",
            data=output,
            file_name=f"Perfil_Carga_{anio}_{mes:02d}.csv",
            mime="text/csv"
        )
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
