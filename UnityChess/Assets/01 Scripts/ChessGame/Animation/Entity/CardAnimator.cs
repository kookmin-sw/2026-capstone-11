using UnityEngine;
using DG.Tweening;

namespace Animations
{
    public class CardAnimator : MonoBehaviour
    {
        [SerializeField] private RectTransform visualRoot;

        [SerializeField] private Animator animator;
        [SerializeField] private Canvas sortingCanvas;

        [Header("Offset")]
        [SerializeField] private float selectedY = 30f;

        [SerializeField] private float selectedScale = 1.05f;

        [SerializeField] private float duration = 0.15f;

        private Tween moveTween;
        private Tween scaleTween;
        private Tween drawTween;
        private Tween useTween;

        private bool isSelected;

        public void SetSelected(bool selected)
        {
            if (isSelected == selected)
                return;

            isSelected = selected;

            PlaySelectionAnimation(selected);
        }

        private void PlaySelectionAnimation(bool selected)
        {
            moveTween?.Kill();
            scaleTween?.Kill();

            float targetY = selected ? selectedY : 0f;
            float targetScale = selected ? selectedScale : 1f;
            
            sortingCanvas.sortingOrder = selected ? 1 : 0;

            moveTween = visualRoot
                .DOLocalMoveY(targetY, duration)
                .SetEase(Ease.OutQuad);

            scaleTween = visualRoot
                .DOScale(targetScale, duration)
                .SetEase(Ease.OutQuad);
        }

        public void PlayDraw()
        {
            drawTween?.Kill();

            Vector2 targetPos = visualRoot.anchoredPosition;

            visualRoot.anchoredPosition = targetPos + Vector2.down * 300f;
            visualRoot.localScale = Vector3.one * 0.6f;

            drawTween = DOTween.Sequence()
                .Append(visualRoot.DOAnchorPos(targetPos, 0.45f)).SetEase(Ease.OutCubic)
                .Join(visualRoot.DOScale(1.05f, 0.35f)).SetEase(Ease.OutCubic)
                .Append(visualRoot.DOScale(1f, 0.12f));
        }

        public void PlayUse(float duration)
        {
            useTween?.Kill();

            useTween = DOTween.Sequence()
                .Append(visualRoot.DOAnchorPos(Vector2.up * 220f, duration * 0.3f).SetEase(Ease.InQuad))
                .Append(visualRoot.DOScale(0.1f, duration).SetEase(Ease.InBack))
                .Join(visualRoot.GetComponent<CanvasGroup>().DOFade(0f, duration * 0.3f))
                .OnComplete(() => { Destroy(gameObject); });
        }

        public void PlayFlash()
        {
            animator.Play("Flash");
        }
    }
}