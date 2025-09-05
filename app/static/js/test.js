// Тестовый файл для проверки работы статических файлов
console.log('✅ Статические файлы загружаются корректно!');

// Проверка доступности BacktestManager
if (typeof window.BacktestManager !== 'undefined') {
    console.log('✅ BacktestManager доступен глобально');
} else {
    console.log('❌ BacktestManager не найден');
}

if (typeof window.backtestManager !== 'undefined') {
    console.log('✅ Экземпляр backtestManager создан');
} else {
    console.log('❌ Экземпляр backtestManager не найден');
}

if (typeof window.testTemplateParameters === 'function') {
    console.log('✅ Функция testTemplateParameters доступна');
} else {
    console.log('❌ Функция testTemplateParameters не найдена');
}
