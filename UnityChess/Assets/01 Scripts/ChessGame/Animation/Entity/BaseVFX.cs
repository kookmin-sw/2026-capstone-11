using UnityEngine;

namespace Animations
{
    public class BaseVFX : MonoBehaviour
    {
        public void OnEndAnimation()
        {
            Destroy(gameObject);
        }
    }
}
