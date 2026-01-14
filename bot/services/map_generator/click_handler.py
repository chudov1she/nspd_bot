"""
Обработчик кликов по элементам через Playwright локаторы.
Использует Playwright локаторы для работы с Shadow DOM.
"""
import asyncio
from loguru import logger


class ClickHandler:
    """Обработчик кликов по кнопкам через Playwright локаторы."""
    
    def __init__(self, page):
        self._page = page
    
    async def click_cadastral_button(self, cadastral_number: str) -> bool:
        """
        Кликает на кнопку с кадастровым номером внутри аккордеона.
        Использует Playwright локаторы - они автоматически работают с Shadow DOM!
        
        Args:
            cadastral_number: Кадастровый номер для поиска
            
        Returns:
            True если клик выполнен успешно, False иначе
        """
        logger.debug("Ищем кнопку с кадастровым номером через Playwright локаторы...")
        button_clicked = False
        
        try:
            # Ждем появления аккордеона
            await self._page.wait_for_selector("m-accordion", timeout=15000)
            
            # Способ 1: Ищем кнопку по тексту с кадастровым номером
            # Playwright автоматически проникает через Shadow DOM!
            search_text = f"Земельный участок: {cadastral_number}"
            
            try:
                # Пробуем найти кнопку по полному тексту
                button_locator = self._page.locator('m-accordion').locator(f'button:has-text("{search_text}")')
                await button_locator.wait_for(state='visible', timeout=9000)
                await button_locator.scroll_into_view_if_needed()
                await button_locator.click()
                logger.info(f"✅ Кнопка найдена и кликнута по тексту '{search_text}'")
                button_clicked = True
            except Exception as e1:
                logger.debug(f"Поиск по полному тексту не сработал: {e1}")
                
                # Способ 2: Ищем кнопку, содержащую кадастровый номер
                try:
                    button_locator = self._page.locator('m-accordion').locator(f'button:has-text("{cadastral_number}")')
                    await button_locator.wait_for(state='visible', timeout=9000)
                    await button_locator.scroll_into_view_if_needed()
                    await button_locator.click()
                    logger.info(f"✅ Кнопка найдена и кликнута по кадастровому номеру '{cadastral_number}'")
                    button_clicked = True
                except Exception as e2:
                    logger.debug(f"Поиск по кадастровому номеру не сработал: {e2}")
                    
                    # Способ 3: Ищем любую кнопку с классом accordion-item.clickable
                    try:
                        button_locator = self._page.locator('m-accordion').locator('button.accordion-item.clickable').first
                        await button_locator.wait_for(state='visible', timeout=9000)
                        
                        # Проверяем, содержит ли текст кнопки кадастровый номер
                        button_text = await button_locator.text_content()
                        if cadastral_number in button_text or search_text in button_text:
                            await button_locator.scroll_into_view_if_needed()
                            await button_locator.click()
                            logger.info(f"✅ Кнопка найдена и кликнута (первая кнопка с нужным текстом): {button_text[:50]}...")
                            button_clicked = True
                        else:
                            logger.warning(f"Первая кнопка не содержит кадастровый номер. Текст: {button_text[:50]}...")
                    except Exception as e3:
                        logger.warning(f"Поиск первой кнопки не сработал: {e3}")
            
            if button_clicked:
                logger.info("✅ Клик выполнен успешно, ждем загрузки карты...")
                await asyncio.sleep(3)  # Ждем загрузки карты после клика
            else:
                logger.warning("⚠️ Не удалось найти и кликнуть на кнопку")
                
        except Exception as e:
            logger.error(f"Ошибка при поиске и клике на кнопку: {e}")
            # Последняя попытка - клик по любому элементу с кадастровым номером
            try:
                await self._page.click(f"text={cadastral_number}", timeout=6000)
                logger.debug("Кликнут на элемент с кадастровым номером")
                await asyncio.sleep(3)
                button_clicked = True
            except:
                logger.warning("Все способы клика не сработали")
        
        return button_clicked

