using UnityEngine;

public class NewMonoBehaviourScript : MonoBehaviour
{
    public Transform tf;
    Vector2 start, end;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        start = tf.localPosition;
        end = new Vector2(0, 1000);
    }

    // Update is called once per frame
    void Update()
    {
        tf.localPosition = Vector2.Lerp(start, end, Time.deltaTime * 0.1f);
    }
}
