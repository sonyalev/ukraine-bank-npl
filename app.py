import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

# 1. Налаштування сторінки
st.set_page_config(
    page_title='Аналіз кредитного ризику банків України', layout='wide'
)

st.title('Динаміка кредитного портфеля та NPL банків України (2025)')


# 2. Завантаження даних із кешуванням
@st.cache_data
def load_data():
    df = pd.read_csv('data_ready_for_charts.csv')
    df['Report_Date'] = pd.to_datetime(df['Report_Date']).dt.strftime(
        '%Y-%m-%d'
    )
    return df


df = load_data()

# -----------------------------------------------------------------------------
# 3. БІЧНЕ МЕНЮ (SIDEBAR) З ФІЛЬТРАМИ
# -----------------------------------------------------------------------------
st.sidebar.header('Фільтри')

# Список усіх банків
all_banks = sorted(df['Bank'].dropna().unique().tolist())

# Мультиселект банків (за замовчуванням вибрано ВСІ)
selected_banks = st.sidebar.multiselect(
    'Оберіть банк(и):', options=all_banks, default=all_banks
)

# Перемикач метрики
metric_option = st.sidebar.radio(
    'Показник:', options=['Заборгованість', 'Кредитний ризик'], index=0
)

# -----------------------------------------------------------------------------
# 4. ФІЛЬТРАЦІЯ ТА АГРЕГАЦІЯ ДАНИХ
# -----------------------------------------------------------------------------
filtered_df = df[df['Bank'].isin(selected_banks)].copy()

if metric_option == 'Заборгованість':
    filtered_df = filtered_df[
        filtered_df['Metric'].str.contains(
            'заборгованості', case=False, na=False
        )
    ]
else:
    filtered_df = filtered_df[
        filtered_df['Metric'].str.contains('ризик', case=False, na=False)
    ]

# Групування за датою та статусом активу
monthly_data = (
    filtered_df.groupby(['Report_Date', 'Asset_Status'])['Value']
    .sum()
    .unstack(fill_value=0)
    .reset_index()
)

# Захист від відсутності колонок
for col in ['Працюючий', 'Непрацюючий (NPL)']:
    if col not in monthly_data.columns:
        monthly_data[col] = 0

# Розрахунок підсумків та % NPL
monthly_data['Усього'] = (
    monthly_data['Працюючий'] + monthly_data['Непрацюючий (NPL)']
)
monthly_data['% NPL'] = (
    monthly_data['Непрацюючий (NPL)'] / monthly_data['Усього']
) * 100
monthly_data['% NPL'] = monthly_data['% NPL'].fillna(0)

# -----------------------------------------------------------------------------
# 5. КЛЮЧОВІ МЕТРИКИ (KPI Cards)
# -----------------------------------------------------------------------------
if not monthly_data.empty:
    latest_date = monthly_data['Report_Date'].max()
    latest_row = monthly_data[
        monthly_data['Report_Date'] == latest_date
    ].iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric(
        'Загальний портфель (тис. грн)',
        f"{latest_row['Усього']:,.0f}".replace(',', ' '),
    )
    col2.metric(
        'Обсяг NPL (тис. грн)',
        f"{latest_row['Непрацюючий (NPL)']:,.0f}".replace(',', ' '),
    )
    col3.metric('Частка NPL (%)', f"{latest_row['% NPL']:.2f}%")

st.markdown('---')

# -----------------------------------------------------------------------------
# 6. ВІДОБРАЖЕННЯ ГРАФІКІВ
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(
    [' Динаміка портфеля (Обсяги)', ' Частка проблемних кредитів (% NPL)']
)

with tab1:
    fig_bar = go.Figure()
    fig_bar.add_trace(
        go.Bar(
            x=monthly_data['Report_Date'],
            y=monthly_data['Працюючий'],
            name='Працюючі',
            marker_color='#2ca02c',
        )
    )
    fig_bar.add_trace(
        go.Bar(
            x=monthly_data['Report_Date'],
            y=monthly_data['Непрацюючий (NPL)'],
            name='Непрацюючі (NPL)',
            marker_color='#d62728',
        )
    )

    fig_bar.update_layout(
        barmode='stack',
        title='Динаміка кредитного портфеля за місяцями (тис. грн)',
        xaxis_title='Дата звітності',
        yaxis_title='Сума (тис. грн)',
        hovermode='x unified',
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    fig_line = px.line(
        monthly_data,
        x='Report_Date',
        y='% NPL',
        title='Динаміка частки NPL у портфелі (%)',
        markers=True,
    )
    fig_line.update_traces(
        line_color='#d62728', line_width=3, marker_size=8
    )
    fig_line.update_layout(
        xaxis_title='Дата звітності', yaxis_title='% NPL', hovermode='x'
    )
    st.plotly_chart(fig_line, use_container_width=True)

# 7. Таблиця з деталізацією
st.subheader('Деталізовані дані за місяцями')
st.dataframe(
    monthly_data.style.format({'% NPL': '{:.2f}%'}), use_container_width=True
)