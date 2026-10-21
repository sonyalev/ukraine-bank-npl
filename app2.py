import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# 1. Налаштування сторінки
st.set_page_config(
    page_title='Аналіз кредитного ризику та покриття NPL', layout='wide'
)

st.title(' Аналіз якості активів та покриття кредитного ризику (2025–2026)')


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

all_banks = sorted(df['Bank'].dropna().unique().tolist())
selected_banks = st.sidebar.multiselect(
    'Оберіть банк(и) для загального аналізу:',
    options=all_banks,
    default=all_banks,
)

metric_option = st.sidebar.radio(
    'Показник для першої вкладки:',
    options=['Заборгованість', 'Кредитний ризик'],
    index=0,
)

# -----------------------------------------------------------------------------
# 4. Вкладки додатка (TABS)
# -----------------------------------------------------------------------------
tab_main, tab_coverage = st.tabs(
    [' Портфель та % NPL', ' Покриття NPL (Ощадбанк vs Система)']
)

# =============================================================================
# ВКЛАДКА 1: Динаміка портфеля та частка NPL
# =============================================================================
with tab_main:
    filtered_df = df[df['Bank'].isin(selected_banks)].copy()

    if metric_option == 'Заборгованість':
        filtered_df = filtered_df[
            filtered_df['Metric'].str.contains(
                'заборгован', case=False, na=False
            )
        ]
    else:
        filtered_df = filtered_df[
            filtered_df['Metric'].str.contains('ризик', case=False, na=False)
        ]

    monthly_data = (
        filtered_df.groupby(['Report_Date', 'Asset_Status'])['Value']
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )

    for col in ['Працюючий', 'Непрацюючий (NPL)']:
        if col not in monthly_data.columns:
            monthly_data[col] = 0

    monthly_data['Усього'] = (
        monthly_data['Працюючий'] + monthly_data['Непрацюючий (NPL)']
    )
    monthly_data['% NPL'] = (
        monthly_data['Непрацюючий (NPL)'] / monthly_data['Усього']
    ) * 100
    monthly_data['% NPL'] = monthly_data['% NPL'].fillna(0)

    # KPI Картки
    if not monthly_data.empty:
        latest_date = monthly_data['Report_Date'].max()
        latest_row = monthly_data[
            monthly_data['Report_Date'] == latest_date
        ].iloc[0]

        k1, k2, k3 = st.columns(3)
        k1.metric(
            'Загальний портфель (тис. грн)',
            f"{latest_row['Усього']:,.0f}".replace(',', ' '),
        )
        k2.metric(
            'Обсяг NPL (тис. грн)',
            f"{latest_row['Непрацюючий (NPL)']:,.0f}".replace(',', ' '),
        )
        k3.metric('Частка NPL (%)', f"{latest_row['% NPL']:.2f}%")

    st.markdown('---')

    sub_tab1, sub_tab2 = st.tabs(
        ['Динаміка портфеля (Обсяги)', 'Частка проблемних кредитів (% NPL)']
    )

    with sub_tab1:
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
            title='Динаміка кредитного портфеля (тис. грн)',
            xaxis_title='Дата звітності',
            yaxis_title='Сума (тис. грн)',
            hovermode='x unified',
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with sub_tab2:
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

# =============================================================================
# ВКЛАДКА 2: Аналіз покриття NPL (Ощадбанк vs Система)
# =============================================================================
with tab_coverage:
    st.subheader('Рівень покриття непрацюючих активів (NPL) резервами')

    # 1. Відбірка тільки NPL рядків
    npl_only = df[df['Asset_Status'] == 'Непрацюючий (NPL)'].copy()

    # 2. Розділення на Заборгованість та Кредитний ризик через pivot
    npl_pivot = (
        npl_only.groupby(['Report_Date', 'Bank', 'Is_Oschad', 'Metric'])[
            'Value'
        ]
        .sum()
        .unstack(level='Metric')
        .reset_index()
    )

    # Знаходимо потрібні стовпчики незалежно від дрібних відмінностей назви
    debt_col = [c for c in npl_pivot.columns if 'заборгован' in str(c).lower()][
        0
    ]
    risk_col = [c for c in npl_pivot.columns if 'ризик' in str(c).lower()][0]

    npl_pivot = npl_pivot.rename(
        columns={debt_col: 'NPL_Debt', risk_col: 'NPL_Risk'}
    )

    # 3. Агрегація по Всій системі
    sys_cov = (
        npl_pivot.groupby('Report_Date')[['NPL_Debt', 'NPL_Risk']]
        .sum()
        .reset_index()
    )
    sys_cov['Coverage_%'] = (sys_cov['NPL_Risk'] / sys_cov['NPL_Debt']) * 100
    sys_cov['Група'] = 'Банківська система в цілому'

    # 4. Агрегація по Ощадбанку
    oschad_cov = (
        npl_pivot[npl_pivot['Is_Oschad'] == True]
        .groupby('Report_Date')[['NPL_Debt', 'NPL_Risk']]
        .sum()
        .reset_index()
    )
    oschad_cov['Coverage_%'] = (
        oschad_cov['NPL_Risk'] / oschad_cov['NPL_Debt']
    ) * 100
    oschad_cov['Група'] = 'АТ "Ощадбанк"'

    # 5. Об'єднання в один DataFrame для побудови графіка
    cov_final = pd.concat(
        [
            sys_cov[['Report_Date', 'Група', 'Coverage_%', 'NPL_Debt', 'NPL_Risk']],
            oschad_cov[
                ['Report_Date', 'Група', 'Coverage_%', 'NPL_Debt', 'NPL_Risk']
            ],
        ],
        ignore_index=True,
    )

    # KPI картки для покриття за останній місяць
    latest_cov_date = cov_final['Report_Date'].max()
    sys_last = cov_final[
        (cov_final['Report_Date'] == latest_cov_date)
        & (cov_final['Група'] == 'Банківська система в цілому')
    ].iloc[0]['Coverage_%']
    oschad_last = cov_final[
        (cov_final['Report_Date'] == latest_cov_date)
        & (cov_final['Група'] == 'АТ "Ощадбанк"')
    ].iloc[0]['Coverage_%']

    c1, c2 = st.columns(2)
    c1.metric(
        'Покриття NPL по Системі (%)',
        f'{sys_last:.2f}%',
        help='Частка резервів до суми NPL',
    )
    c2.metric('Покриття NPL в Ощадбанку (%)', f'{oschad_last:.2f}%')

    st.markdown('---')

    # Побудова порівняльного лінійного графіка
    fig_cov = px.line(
        cov_final,
        x='Report_Date',
        y='Coverage_%',
        color='Група',
        title='Порівняльна динаміка рівня покриття NPL кредитним ризиком (%)',
        markers=True,
        color_discrete_map={
            'АТ "Ощадбанк"': '#d62728',
            'Банківська система в цілому': '#1f77b4',
        },
    )

    fig_cov.update_traces(line_width=3, marker_size=8)
    fig_cov.update_layout(
        xaxis_title='Дата звітності',
        yaxis_title='Рівень покриття (%)',
        hovermode='x unified',
        legend_title_text='',
    )

    st.plotly_chart(fig_cov, use_container_width=True)

    # Детальна таблиця
    with st.expander(' Переглянути детальні цифри розрахунку покриття'):
        st.dataframe(
            cov_final.pivot(
                index='Report_Date',
                columns='Група',
                values=['NPL_Debt', 'NPL_Risk', 'Coverage_%'],
            ).style.format(
                {
                    ('Coverage_%', 'АТ "Ощадбанк"'): '{:.2f}%',
                    ('Coverage_%', 'Банківська система в цілому'): '{:.2f}%',
                }
            ),
            use_container_width=True,
        )