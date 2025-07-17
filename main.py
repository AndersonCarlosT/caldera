import streamlit as st
import pandas as pd
import io

st.title("📊 Lector de archivos .LP - Filtro por Mes, Feriados y HP/HFP")

archivo_lp = st.file_uploader("Sube tu archivo .LP", type=["lp"])

if archivo_lp is not None:
    contenido = archivo_lp.read().decode('utf-8')
    lineas = contenido.splitlines()

    # Buscar inicio de la tabla
    indice_inicio = None
    for i, linea in enumerate(lineas):
        if linea.strip().startswith("Fecha/Hora"):
            indice_inicio = i
            break

    if indice_inicio is None:
        st.error("No se encontró la cabecera 'Fecha/Hora' en el archivo.")
    else:
        # Leer tabla
        tabla = "\n".join(lineas[indice_inicio:])
        df = pd.read_csv(io.StringIO(tabla), sep=";", engine='python')

        # Limpiar columnas y espacios
        df.columns = [col.strip() for col in df.columns]
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.dropna(axis=1, how='all')

        # Convertir a datetime
        df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], format='%d/%m/%Y %H:%M:%S')

        # Selector de mes
        meses = {
            "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
            "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
            "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
        }

        mes_seleccionado = st.selectbox("Selecciona el mes a filtrar", list(meses.keys()))
        numero_mes = meses[mes_seleccionado]

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

        # Filtrar por mes
        df_mes = df[df['Fecha/Hora'].dt.month == numero_mes]

        # Separar fecha y hora
        df_mes['Fecha'] = df_mes['Fecha/Hora'].dt.strftime('%d/%m/%Y')
        df_mes['Hora'] = df_mes['Fecha/Hora'].dt.strftime('%H:%M:%S')

        # Clasificación HP / HFP según rango 15 min
        def clasificar_horario(hora_str):
            hora = pd.to_datetime(hora_str, format='%H:%M:%S').time()
            if hora >= pd.to_datetime("23:15:00", format='%H:%M:%S').time() or hora <= pd.to_datetime("18:00:00", format='%H:%M:%S').time():
                return "HFP"
            else:
                return "HP"

        df_mes['Horario'] = df_mes['Hora'].apply(clasificar_horario)

        # Mostrar dataframe filtrado con clasificación
        st.success(f"Datos del mes de {mes_seleccionado} con clasificación HP/HFP")
        st.write(f"Días feriados ingresados: {dias_feriados}")
        st.dataframe(df_mes[['Fecha', 'Hora', 'Horario'] + [col for col in df_mes.columns if col not in ['Fecha/Hora', 'Fecha', 'Hora', 'Horario']]])
