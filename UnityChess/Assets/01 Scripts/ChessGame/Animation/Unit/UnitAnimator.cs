using UnityEngine;
using DG.Tweening;

namespace Animations.Unit
{
    public class UnitAnimator : MonoBehaviour
    {
        [SerializeField] private Transform visualRoot;
        [SerializeField] private Animator animator;
        [SerializeField] private SpriteRenderer unitSprite;

        [SerializeField] private Material dissolveMaterial;

        private Tween moveTween;
        private Tween DamageTween;

        public void PlayMove(Vector3 targetPosition, float duration)
        {
            moveTween?.Kill();

            moveTween = transform
                .DOMove(targetPosition, duration)
                .SetEase(Ease.InOutQuad);
        }

        public void PlayDamage()
        {
            DamageTween?.Kill();

            // 간단한 피격 애니메이션: 좌우로 흔들리는 효과
            Vector3 originalPosition = transform.position;
            float shakeAmount = 0.05f;

            DamageTween = DOTween.Sequence()
                .Append(transform.DOMoveX(originalPosition.x - shakeAmount, 0.1f).SetEase(Ease.InOutQuad))
                .Append(transform.DOMoveX(originalPosition.x + shakeAmount, 0.1f).SetEase(Ease.InOutQuad))
                .Join(unitSprite.DOColor(Color.red, 0.1f).SetEase(Ease.InOutQuad)).SetLoops(2, LoopType.Yoyo)
                .Append(transform.DOMoveX(originalPosition.x, 0.1f).SetEase(Ease.InOutQuad));
        }

        public void PlayDeploy()
        {
            animator.Play("Deploy");
        }

        public void PlayDestroy(float duration)
        {
            var runtimeMaterial = new Material(dissolveMaterial);

            unitSprite.material = runtimeMaterial;

            runtimeMaterial.SetFloat("_Fade", 1f);

            // Tween
            DOTween.To(
                () => runtimeMaterial.GetFloat("_Fade"),
                x => runtimeMaterial.SetFloat("_Fade", x),
                0f,
                duration
            )
            .SetEase(Ease.InQuad)
            .OnComplete(() => { Destroy(gameObject); });
        }
    }
}