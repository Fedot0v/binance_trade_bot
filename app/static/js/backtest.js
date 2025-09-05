/**
 * Модуль для работы с бэктестом
 * Содержит всю логику для управления параметрами шаблонов и формой бэктеста
 */

class BacktestManager {
    constructor() {
        this.templatesData = [];
        this.form = null;
        this.loadingModal = null;
        this.templateSelect = null;
        this.templateParametersSection = null;
        this.templateParametersDisplay = null;
        this.progressBar = null;

        this.init();
    }

    init() {
        console.log('🚀 BacktestManager инициализирован');

        // Получаем DOM элементы
        this.form = document.getElementById('backtestForm');
        this.loadingModal = document.getElementById('loadingModal');
        this.templateSelect = document.getElementById('template_id');
        this.templateParametersSection = document.getElementById('template-parameters-section');
        this.templateParametersDisplay = document.getElementById('template-parameters-display');
        this.progressBar = document.querySelector('.progress-bar');

        // Проверяем элементы
        console.log('🔍 Проверка DOM элементов:');
        console.log('templateSelect:', this.templateSelect);
        console.log('templateParametersSection:', this.templateParametersSection);
        console.log('templateParametersDisplay:', this.templateParametersDisplay);

        // Настраиваем обработчики событий
        this.setupEventListeners();

        // Восстанавливаем сохраненные параметры
        this.restoreSavedParameters();
    }

    setupEventListeners() {
        if (this.templateSelect) {
            console.log('✅ templateSelect найден, добавляем обработчик');
            this.templateSelect.addEventListener('change', (e) => {
                this.handleTemplateChange(e);
            });
        } else {
            console.error('❌ templateSelect не найден!');
        }

        // Обработчики для кнопок редактирования параметров
        this.setupParameterEditHandlers();

        // Обработчик отправки формы
        if (this.form) {
            this.form.addEventListener('submit', (e) => {
                this.handleFormSubmit(e);
            });
        }
    }

    handleTemplateChange(event) {
        console.log('🎯 Сработал обработчик изменения шаблона');
        console.log('📋 Выбранное значение:', event.target.value);

        const selectedValue = event.target.value;
        if (selectedValue) {
            console.log('✅ Выбран шаблон с ID:', selectedValue);

            // Скрываем все описания
            document.querySelectorAll('.template-desc').forEach(desc => {
                desc.style.display = 'none';
            });

            // Показываем выбранное описание
            const desc = document.getElementById('desc-' + selectedValue);
            if (desc) {
                desc.style.display = 'block';
                console.log('📝 Показываем описание шаблона');
            } else {
                console.log('⚠️ Описание шаблона не найдено');
            }

            // Загружаем параметры шаблона
            console.log('🚀 Загружаем параметры шаблона');
            this.loadTemplateParameters(selectedValue);
        } else {
            console.log('❌ Шаблон не выбран, скрываем секцию параметров');
            if (this.templateParametersSection) {
                this.templateParametersSection.style.display = 'none';
            }
        }
    }

    async loadTemplateParameters(templateId) {
        try {
            console.log('🚀 loadTemplateParameters вызвана с ID:', templateId);

            // Получаем данные шаблона
            const templateData = this.templatesData.find(template => template.id == templateId);
            console.log('📋 Найденный шаблон:', templateData);

            if (templateData && templateData.parameters) {
                console.log('✅ Найдены параметры шаблона:', templateData.parameters);
                this.displayTemplateParameters(templateData.parameters);
                if (this.templateParametersSection) {
                    this.templateParametersSection.style.display = 'block';
                }
            } else {
                console.log('⚠️ Параметры шаблона не найдены или пустые');
                if (this.templateParametersSection) {
                    this.templateParametersSection.style.display = 'none';
                }
            }

        } catch (error) {
            console.error('❌ Ошибка при загрузке параметров шаблона:', error);
            if (this.templateParametersSection) {
                this.templateParametersSection.style.display = 'none';
            }
        }
    }

    displayTemplateParameters(parameters) {
        console.log('🎨 displayTemplateParameters вызвана с параметрами:', parameters);

        if (!this.templateParametersDisplay) {
            console.error('❌ templateParametersDisplay не найден');
            return;
        }

        console.log('✅ templateParametersDisplay найден, отображаем параметры');

        let html = '<div class="row">';

        Object.entries(parameters).forEach(([key, value]) => {
            const displayValue = this.isPercentageParameter(key) ?
                `${(parseFloat(value) * 100).toFixed(2)}%` : value;

            html += `
                <div class="col-md-6 mb-2">
                    <div class="parameter-item">
                        <strong class="parameter-label">${this.formatParameterName(key)}:</strong>
                        <span class="badge badge-secondary parameter-value">${displayValue}</span>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        this.templateParametersDisplay.innerHTML = html;
    }

    isPercentageParameter(key) {
        const percentageParams = ['deposit_prct', 'stop_loss_pct', 'take_profit_pct',
                                'btc_deposit_prct', 'eth_deposit_prct', 'btc_stop_loss_pct', 'eth_stop_loss_pct', 'trailing_stop_pct'];
        return percentageParams.includes(key);
    }

    formatPercentageDisplay(value) {
        if (!value || value === '') {
            return '(0.0%)';
        }

        try {
            const numValue = parseFloat(value);
            if (!isNaN(numValue)) {
                const percentage = (numValue * 100).toFixed(2);
                return `(${percentage}%)`;
            } else {
                return `(${value})`;
            }
        } catch (error) {
            return `(${value})`;
        }
    }

    setupPercentageListeners() {
        // Находим все поля с процентными параметрами
        const percentageInputs = document.querySelectorAll('input[data-percentage-param="true"]');

        percentageInputs.forEach(input => {
            const displaySpan = document.getElementById(`percentage-display-${input.name.replace('param_', '')}`);

            if (displaySpan) {
                const updatePercentageDisplay = () => {
                    const value = input.value.trim();
                    displaySpan.textContent = this.formatPercentageDisplay(value);
                };

                // Обновляем при изменении значения
                input.addEventListener('input', updatePercentageDisplay);
                input.addEventListener('change', updatePercentageDisplay);
                input.addEventListener('blur', updatePercentageDisplay);

                // Инициализируем отображение
                updatePercentageDisplay();
            }
        });

        console.log('✅ Настроены обработчики для динамических процентов');
    }

    formatParameterName(key) {
        const nameMap = {
            'ema_fast': 'Быстрая EMA',
            'ema_slow': 'Медленная EMA',
            'trend_threshold': 'Порог тренда',
            'deposit_prct': 'Депозит (%)',
            'stop_loss_pct': 'Стоп-лосс (%)',
            'take_profit_pct': 'Тейк-профит (%)',
            'trailing_stop_pct': 'Трейлинг-стоп (%)',
            'btc_deposit_prct': 'BTC Депозит (%)',
            'eth_deposit_prct': 'ETH Депозит (%)',
            'btc_stop_loss_pct': 'BTC Стоп-лосс (%)',
            'eth_stop_loss_pct': 'ETH Стоп-лосс (%)'
        };
        return nameMap[key] || key;
    }

    setupParameterEditHandlers() {
        const editBtn = document.getElementById('edit-parameters-btn');
        const saveBtn = document.getElementById('save-parameters-btn');
        const cancelBtn = document.getElementById('cancel-edit-btn');

        if (editBtn) {
            editBtn.addEventListener('click', () => {
                this.startParameterEditing();
            });
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                this.saveParameterChanges();
            });
        }

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.cancelParameterEditing();
            });
        }
    }

    startParameterEditing() {
        const selectedTemplateId = this.templateSelect ? this.templateSelect.value : null;
        if (!selectedTemplateId) return;

        const currentParameters = this.getTemplateParametersFromData(selectedTemplateId);
        this.createParameterEditForm(currentParameters);

        // Переключаем видимость
        const displayDiv = document.getElementById('template-parameters-display');
        const editDiv = document.getElementById('template-parameters-edit');
        const editBtn = document.getElementById('edit-parameters-btn');

        if (displayDiv) displayDiv.style.display = 'none';
        if (editDiv) editDiv.style.display = 'block';
        if (editBtn) editBtn.style.display = 'none';
    }

    createParameterEditForm(parameters) {
        const formDiv = document.getElementById('parameters-form');
        if (!formDiv) return;

        let html = '<div class="row">';

        Object.entries(parameters).forEach(([key, value]) => {
            let inputType = 'text';
            let step = 'any';

            if (key.includes('ema')) {
                inputType = 'number';
                step = '1';
            }

            const displayValue = value;
            const isPercentage = this.isPercentageParameter(key);

            html += `
                <div class="col-md-6 mb-3">
                    <label for="param_${key}" class="form-label">${this.formatParameterName(key)}</label>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <input type="${inputType}" class="form-control form-control-sm" id="param_${key}"
                               name="param_${key}" value="${displayValue}" step="${step}"
                               ${isPercentage ? 'data-percentage-param="true"' : ''}>
                        ${isPercentage ? `
                            <span style="color: #F0B90B; font-weight: bold; white-space: nowrap; min-width: 60px;"
                                  data-percentage-display id="percentage-display-${key}">
                                ${this.formatPercentageDisplay(displayValue)}
                            </span>
                        ` : ''}
                    </div>
                    ${isPercentage ? '<small class="form-text text-muted">В дробях (видно в % справа)</small>' : ''}
                </div>
            `;
        });

        html += '</div>';
        formDiv.innerHTML = html;

        // Добавляем обработчики для динамического обновления процентов
        this.setupPercentageListeners();
    }

    saveParameterChanges() {
        const selectedTemplateId = this.templateSelect ? this.templateSelect.value : null;
        if (!selectedTemplateId) return;

        // Собираем измененные параметры
        const inputs = document.querySelectorAll('#parameters-form input');
        const newParameters = {};

        inputs.forEach(input => {
            const paramName = input.name.replace('param_', '');
            newParameters[paramName] = input.value;
        });

        // Сохраняем параметры
        localStorage.setItem(`template_params_${selectedTemplateId}`, JSON.stringify(newParameters));

        // Добавляем параметры в форму
        this.updateFormWithParameters(newParameters);

        // Обновляем отображение
        this.displayTemplateParameters(newParameters);

        // Переключаем видимость
        this.cancelParameterEditing();

        console.log('✅ Параметры сохранены:', newParameters);
    }

    cancelParameterEditing() {
        const displayDiv = document.getElementById('template-parameters-display');
        const editDiv = document.getElementById('template-parameters-edit');
        const editBtn = document.getElementById('edit-parameters-btn');

        if (displayDiv) displayDiv.style.display = 'block';
        if (editDiv) editDiv.style.display = 'none';
        if (editBtn) editBtn.style.display = 'inline-block';
    }

    updateFormWithParameters(parameters) {
        // Удаляем старые скрытые поля параметров
        const oldParamFields = document.querySelectorAll('input[name^="custom_param_"]');
        oldParamFields.forEach(field => field.remove());

        // Добавляем новые скрытые поля для параметров
        Object.entries(parameters).forEach(([key, value]) => {
            const hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.name = `custom_param_${key}`;
            hiddenField.value = value;
            if (this.form) {
                this.form.appendChild(hiddenField);
            }
        });

        console.log('📝 Добавлены скрытые поля параметров:', parameters);
    }

    getTemplateParametersFromData(templateId) {
        console.log('🔍 Ищем шаблон с ID:', templateId, 'среди', this.templatesData.length, 'шаблонов');

        const templateData = this.templatesData.find(template => template.id == templateId);
        console.log('📋 Найденный шаблон:', templateData);

        if (templateData && templateData.parameters) {
            console.log('✅ Найдены параметры шаблона:', templateData.parameters);
            return templateData.parameters;
        }

        console.log('⚠️ Параметры шаблона не найдены, используем пустые');
        return {};
    }

    restoreSavedParameters() {
        const selectedTemplateId = this.templateSelect ? this.templateSelect.value : null;
        if (!selectedTemplateId) return;

        const savedParams = localStorage.getItem(`template_params_${selectedTemplateId}`);
        if (savedParams) {
            try {
                const parameters = JSON.parse(savedParams);
                this.displayTemplateParameters(parameters);
                if (this.templateParametersSection) {
                    this.templateParametersSection.style.display = 'block';
                }
                this.updateFormWithParameters(parameters);
                console.log('🔄 Восстановлены сохраненные параметры:', parameters);
            } catch (error) {
                console.error('❌ Ошибка при восстановлении параметров:', error);
            }
        }
    }

    handleFormSubmit(event) {
        console.log('📤 Отправка формы бэктеста');

        // Показываем модальное окно загрузки
        if (this.loadingModal) {
            try {
                const modal = new bootstrap.Modal(this.loadingModal, {
                    backdrop: 'static',
                    keyboard: false
                });
                modal.show();
                console.log('✅ Модальное окно загрузки показано');
            } catch (error) {
                console.error('❌ Ошибка при показе модального окна:', error);
            }
        } else {
            console.error('❌ Модальное окно загрузки не найдено');
        }
    }

    // Метод для тестирования (доступен глобально)
    testParameters() {
        console.log('🧪 Запуск теста параметров шаблона');

        if (!this.templatesData || this.templatesData.length === 0) {
            alert('❌ Данные шаблонов не загружены!');
            return;
        }

        alert(`✅ Найдено ${this.templatesData.length} шаблонов\n\nПроверьте консоль браузера для подробной информации.`);

        // Тестируем первый шаблон
        if (this.templatesData.length > 0) {
            const firstTemplate = this.templatesData[0];
            console.log('🎯 Тестируем первый шаблон:', firstTemplate);

            // Имитируем выбор шаблона
            if (this.templateSelect) {
                this.templateSelect.value = firstTemplate.id;
                this.templateSelect.dispatchEvent(new Event('change'));
            }
        }
    }

    // Метод для установки данных шаблонов (вызывается из шаблона)
    setTemplatesData(data) {
        this.templatesData = data;
        console.log('📊 Данные шаблонов установлены:', data);
    }
}

// Создаем глобальный экземпляр
window.BacktestManager = BacktestManager;
window.backtestManager = new BacktestManager();

// Функция для тестирования (доступна глобально)
window.testTemplateParameters = function() {
    if (window.backtestManager) {
        window.backtestManager.testParameters();
    } else {
        console.error('BacktestManager не инициализирован');
    }
};
