using TMPro;
using UnityEngine;
using UnityEngine.UI;
using core.data;
using ui.tooltip;

public class DeckCardItem : MonoBehaviour
{
    [SerializeField] private Image image;
    [SerializeField] private TMP_Text title;
    [SerializeField] private TMP_Text header;
    [SerializeField] private TMP_Text description;

    public void Bind(CardDefinition card, Sprite sprite)
    {
        image.sprite = sprite;
        
        var descData = TooltipBuilder.CardTooltip(card);

        title.text = descData.title;
        header.text = descData.header;
        description.text = descData.description;
    }
}