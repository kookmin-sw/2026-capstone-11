using core.data;
using DG.Tweening;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class LeaderCarouselItem : MonoBehaviour
{
    [SerializeField] private Image portrait;

    [Header("Tween")]
    [SerializeField] private float duration = 0.2f;
    [SerializeField] private float focusedScale = 1.15f;
    [SerializeField] private float unfocusedScale = 0.8f;
    [SerializeField] private float focusedY = 20f;
    [SerializeField] private float unfocusedY = 0f;

    [SerializeField] private RectTransform rectTransform;

    public int Index { get; private set; }

    public void Bind(int index, Sprite sprite)
    {
        Index = index;

        portrait.sprite = sprite;
    }

    public void SetFocused(bool focused)
    {
        float targetScale = focused ? focusedScale : unfocusedScale;


        float targetY = focused ? focusedY : unfocusedY;

        rectTransform
            .DOScale(targetScale, duration)
            .SetEase(Ease.OutCubic);

        rectTransform
            .DOAnchorPosY(targetY, duration)
            .SetEase(Ease.OutCubic);
    }
}